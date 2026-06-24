"""HTTP API server for desktopclaw."""

import asyncio
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from desktopclaw.bus.events import InboundMessage
from desktopclaw.agent.loop import ProcessResult
from desktopclaw.config.loader import load_config, save_config
from desktopclaw.config.paths import get_media_dir
from desktopclaw.utils.usage import empty_usage_dict
from desktopclaw.api.session_helpers import session_info_dict, session_messages_for_ui
from desktopclaw.api.memory_helpers import build_memory_payload


class APIServer:
    """HTTP API server for chat, settings, and media."""

    @staticmethod
    def _build_complete_event(result: ProcessResult | str | None) -> dict[str, Any]:
        if isinstance(result, ProcessResult):
            event: dict[str, Any] = {
                'type': 'complete',
                'response': result.content,
                'usage': result.usage or empty_usage_dict(),
                'success': result.error is None,
            }
            if result.error:
                event['error'] = result.error
            if result.blocks:
                event['blocks'] = result.blocks
            return event
        text = str(result) if result is not None else ''
        is_err = bool(text) and (
            text.startswith('Error')
            or '超时' in text
            or 'Authentication Fails' in text
        )
        event = {
            'type': 'complete',
            'response': text,
            'usage': empty_usage_dict(),
            'success': not is_err,
        }
        if is_err:
            event['error'] = text
        return event

    def __init__(self, agent, bus, port: int = 3000):
        self.agent = agent
        self.bus = bus
        self.port = port
        self.server = None
        self._feishu_sse_clients: list[asyncio.StreamWriter] = []
        self._feishu_sse_lock = asyncio.Lock()

    async def handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle an incoming HTTP request."""
        client_addr = writer.get_extra_info('peername', ('unknown', 0))
        try:
            # Read the request line with timeout
            request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not request_line:
                return

            request_line = request_line.decode('utf-8').strip()
            parts = request_line.split()
            if len(parts) < 2:
                return

            method, path = parts[0], parts[1]
            print(f"[API] {client_addr[0]} - {method} {path}")

            # Read headers
            headers = {}
            while True:
                header_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if header_line == b'\r\n':
                    break
                line = header_line.decode('utf-8').strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Handle CORS preflight
            if method == 'OPTIONS':
                response = self._cors_response(200)
                writer.write(response.encode())
                await writer.drain()
                print(f"[API] CORS preflight handled")
                return

            # Handle SSE streaming endpoint
            print(f"[API] Checking route: {method} {path}")
            if method == 'GET' and path.startswith('/chat/stream'):
                print(f"[API] Matched SSE stream endpoint")
                query = path.split('?')[1] if '?' in path else ''
                params = {}
                for param in query.split('&'):
                    if '=' in param:
                        k, v = param.split('=', 1)
                        params[k] = unquote(v)  # URL decode the value
                message = params.get('message', '')
                print(f"[API] SSE message: {message[:50]}...")
                if message:
                    await self._handle_sse_stream(writer, message)
                return

            # Handle POST /chat
            if method == 'POST' and path == '/chat':
                await self._handle_chat_request(reader, writer, headers)
                return

            # Handle SSE endpoint for Feishu events
            if method == 'GET' and path == '/feishu/events':
                await self._handle_feishu_sse(writer)
                return

            # Handle health check
            if method == 'GET' and path == '/health':
                response = self._http_response(200, json.dumps({'status': 'ok'}))
                writer.write(response.encode())
                await writer.drain()
                return

            # Handle settings (load/save frontend persona + provider overrides)
            if method == 'GET' and path == '/settings':
                await self._handle_get_settings(writer)
                return
            if method == 'POST' and path == '/settings':
                await self._handle_set_settings(reader, writer, headers)
                return

            if method == 'GET' and path == '/memory':
                await self._handle_get_memory(writer)
                return
            if method == 'POST' and path == '/memory/retry-embedding':
                await self._handle_retry_embedding(writer)
                return

            # Handle session list / messages for frontend history sync
            if method == 'GET' and path == '/sessions':
                await self._handle_list_sessions(writer)
                return
            if method == 'GET' and path.startswith('/sessions/') and path.endswith('/messages'):
                session_key = unquote(path[len('/sessions/'):-len('/messages')])
                await self._handle_get_session_messages(writer, session_key)
                return
            if method == 'DELETE' and path.startswith('/sessions/') and not path.endswith('/messages'):
                session_key = unquote(path[len('/sessions/'):])
                await self._handle_delete_session(writer, session_key)
                return

            # Handle media files
            if method == 'GET' and path.startswith('/media/'):
                await self._handle_media_request(writer, path[7:])
                return

            # Handle audio upload
            if method == 'POST' and path == '/audio/upload':
                await self._handle_audio_upload(reader, writer, headers)
                return

            # 404 Not Found
            print(f"[API] 404 Not Found: {method} {path}")
            response = self._http_response(404, json.dumps({'error': 'Not found'}))
            writer.write(response.encode())
            await writer.drain()

        except asyncio.TimeoutError:
            print(f"[API] Timeout error from {client_addr}")
            try:
                error_body = json.dumps({'success': False, 'error': 'Request timeout'})
                response = self._http_response(408, error_body)
                writer.write(response.encode())
                await writer.drain()
            except:
                pass
        except Exception as e:
            print(f"[API] Error: {e}")
            try:
                error_body = json.dumps({'success': False, 'error': str(e)})
                response = self._http_response(500, error_body)
                writer.write(response.encode())
                await writer.drain()
            except:
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

    async def _handle_sse_stream(self, writer, message):
        """Handle SSE streaming for real-time tool call updates."""
        print(f"[API] SSE stream started for: {message[:50]}...")

        # Send SSE headers
        sse_headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n"
        )
        writer.write(sse_headers.encode())
        await writer.drain()

        # Send initial thinking event
        thinking_event = {'type': 'thinking', 'content': 'AI 正在思考...'}
        writer.write(f"data: {json.dumps(thinking_event, ensure_ascii=False)}\n\n".encode())
        await writer.drain()

        # Create event for completion
        response_received = asyncio.Event()
        final_response = [None]

        async def collect_progress(content: str, *, tool_hint: bool = False) -> None:
            """Collect tool calls and send SSE events."""
            event_type = 'tool_call' if tool_hint else 'progress'
            event = {
                'type': event_type,
                'content': content
            }
            event_data = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            try:
                writer.write(event_data.encode())
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                pass

        async def process_with_agent():
            """Process message through agent."""
            try:
                response = await self.agent.process_direct(
                    message,
                    session_key="api:frontend",
                    channel="api",
                    chat_id="frontend",
                    on_progress=collect_progress
                )
                final_response[0] = response
                response_received.set()
            except Exception as e:
                final_response[0] = f"Error: {str(e)}"
                response_received.set()

        # Start agent processing
        asyncio.create_task(process_with_agent())

        # Wait for response with timeout
        try:
            await asyncio.wait_for(response_received.wait(), timeout=600.0)
        except asyncio.TimeoutError:
            final_response[0] = "请求超时，请稍后重试。(请求处理时间超过10分钟)"

        # Send final response event
        final_event = self._build_complete_event(final_response[0])
        event_data = f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"
        try:
            writer.write(event_data.encode())
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass

        print(f"[API] SSE stream completed")

    async def _handle_media_request(self, writer: asyncio.StreamWriter, file_path: str):
        """Handle media file request."""
        try:
            # Get media directory
            media_dir = get_media_dir("feishu")
            full_path = media_dir / file_path
            
            print(f"[API] Media request: {file_path}")
            print(f"[API] Media dir: {media_dir}")
            print(f"[API] Full path: {full_path}")
            print(f"[API] File exists: {full_path.exists()}")

            # Security check: ensure file is within media directory
            try:
                full_path.resolve().relative_to(media_dir.resolve())
            except ValueError:
                print(f"[API] Access denied: {file_path}")
                response = self._http_response(403, json.dumps({'error': 'Access denied'}))
                writer.write(response.encode())
                await writer.drain()
                return

            if not full_path.exists():
                print(f"[API] File not found: {full_path}")
                response = self._http_response(404, json.dumps({'error': 'File not found'}))
                writer.write(response.encode())
                await writer.drain()
                return

            # Guess content type
            content_type, _ = mimetypes.guess_type(str(full_path))
            if not content_type:
                content_type = 'application/octet-stream'
            
            # Fix for opus files
            if full_path.suffix.lower() == '.opus':
                content_type = 'audio/ogg; codecs=opus'
            
            # Fix for mp3 files
            if full_path.suffix.lower() == '.mp3':
                content_type = 'audio/mpeg'

            # Read file
            data = full_path.read_bytes()

            # Send response
            headers = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(data)}\r\n"
                f"Access-Control-Allow-Origin: *\r\n"
                f"\r\n"
            )
            writer.write(headers.encode())
            writer.write(data)
            await writer.drain()
            print(f"[API] Media file served: {file_path}")

        except Exception as e:
            print(f"[API] Error serving media file: {e}")
            response = self._http_response(500, json.dumps({'error': str(e)}))
            writer.write(response.encode())
            await writer.drain()

    async def _handle_audio_upload(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, headers: dict):
        """Handle audio file upload from frontend."""
        try:
            print("[API] Handling audio upload")
            
            # Read content length
            content_length = int(headers.get('content-length', 0))
            if content_length == 0:
                response = self._http_response(400, json.dumps({'error': 'No content'}))
                writer.write(response.encode())
                await writer.drain()
                return
            
            # Read the multipart body
            body = await reader.read(content_length)
            
            # Parse multipart form data
            content_type = headers.get('content-type', '')
            boundary = None
            if 'boundary=' in content_type:
                boundary = content_type.split('boundary=')[1].split(';')[0].strip()
            
            if not boundary:
                response = self._http_response(400, json.dumps({'error': 'Invalid content type'}))
                writer.write(response.encode())
                await writer.drain()
                return
            
            # Extract audio data from multipart
            body_str = body.decode('latin-1')
            parts = body_str.split('--' + boundary)
            
            audio_data = None
            channel = 'feishu'
            
            for part in parts:
                if 'Content-Disposition' in part and 'filename=' in part:
                    # Find the actual data after headers
                    header_end = part.find('\r\n\r\n')
                    if header_end != -1:
                        audio_data = part[header_end + 4:].rstrip('\r\n')
                        break
                elif 'name="channel"' in part:
                    header_end = part.find('\r\n\r\n')
                    if header_end != -1:
                        channel = part[header_end + 4:].rstrip('\r\n')
            
            if not audio_data:
                response = self._http_response(400, json.dumps({'error': 'No audio data'}))
                writer.write(response.encode())
                await writer.drain()
                return
            
            # Save audio file
            from desktopclaw.config.paths import get_media_dir
            import uuid
            media_dir = get_media_dir("frontend")
            media_dir.mkdir(parents=True, exist_ok=True)
            
            file_name = f"{uuid.uuid4().hex}.webm"
            file_path = media_dir / file_name
            file_path.write_bytes(audio_data.encode('latin-1'))
            
            print(f"[API] Audio saved to: {file_path}")
            
            # Transcribe audio using ASR
            transcription = await self._transcribe_audio(str(file_path))
            
            if transcription:
                print(f"[API] Audio transcription: {transcription}")
                
                response_text = await self.agent.process_direct(transcription, channel)
                response_content = response_text.content if isinstance(response_text, ProcessResult) else response_text
                response_usage = response_text.usage if isinstance(response_text, ProcessResult) else empty_usage_dict()

                tts_audio_path = None
                if response_content:
                    tts_audio_path = await self._synthesize_speech(response_content)
                    
                    # Also send TTS audio to Feishu if enabled
                    if tts_audio_path and self.channel_manager:
                        feishu_channel = self.channel_manager.channels.get("feishu")
                        if feishu_channel and hasattr(feishu_channel, '_synthesize_speech'):
                            try:
                                await feishu_channel._send_tts_to_feishu(response_content, tts_audio_path)
                            except Exception as e:
                                print(f"[API] Failed to send TTS to Feishu: {e}")
                
                result = {
                    'success': True,
                    'transcription': transcription,
                    'response': response_content,
                    'usage': response_usage,
                    'ttsAudio': tts_audio_path,
                }
            else:
                result = {
                    'success': False,
                    'error': 'Failed to transcribe audio'
                }
            
            response = self._http_response(200, json.dumps(result))
            writer.write(response.encode())
            await writer.drain()
            
        except Exception as e:
            print(f"[API] Error handling audio upload: {e}")
            import traceback
            traceback.print_exc()
            response = self._http_response(500, json.dumps({'error': str(e)}))
            writer.write(response.encode())
            await writer.drain()

    async def _handle_get_settings(self, writer):
        """Return the frontend-relevant settings subset (camelCase)."""
        try:
            config = load_config()
            defaults = config.agents.defaults
            custom = config.providers.custom
            feishu = config.channels.feishu
            payload = {
                'baseUrl': custom.api_base or '',
                'modelId': defaults.model,
                'fastModelId': defaults.fast_model or '',
                'apiKey': custom.api_key or '',
                'personality': defaults.personality,
                'customPrompt': defaults.custom_prompt,
                'birthday': defaults.birthday,
                'feishu': {
                    'asrEnabled': feishu.asr_enabled,
                    'ttsEnabled': feishu.tts_enabled,
                    'ttsVoice': feishu.tts_voice,
                },
            }
            response = self._http_response(200, json.dumps(payload, ensure_ascii=False))
            writer.write(response.encode())
            await writer.drain()
        except Exception as e:
            print(f"[API] Error reading settings: {e}")
            body = json.dumps({'success': False, 'error': str(e)})
            response = self._http_response(500, body)
            writer.write(response.encode())
            await writer.drain()

    async def _handle_set_settings(self, reader, writer, headers):
        """Persist frontend-supplied settings to the config file.

        Accepts camelCase keys matching the GET response. Only whitelisted
        fields are written; unknown keys are ignored.
        """
        try:
            content_length = int(headers.get('content-length', 0))
            if content_length <= 0:
                body = json.dumps({'success': False, 'error': 'Empty body'})
                response = self._http_response(400, body)
                writer.write(response.encode())
                await writer.drain()
                return

            raw = await reader.read(content_length)
            try:
                data = json.loads(raw.decode('utf-8'))
            except json.JSONDecodeError as e:
                body = json.dumps({'success': False, 'error': f'Invalid JSON: {e}'})
                response = self._http_response(400, body)
                writer.write(response.encode())
                await writer.drain()
                return

            config = load_config()
            defaults = config.agents.defaults
            custom = config.providers.custom
            feishu = config.channels.feishu

            # Scalars
            if 'modelId' in data and isinstance(data['modelId'], str):
                defaults.model = data['modelId']
            if 'fastModelId' in data and isinstance(data['fastModelId'], str):
                defaults.fast_model = data['fastModelId']
            if 'baseUrl' in data and isinstance(data['baseUrl'], str):
                custom.api_base = data['baseUrl'] or None
            if 'apiKey' in data and isinstance(data['apiKey'], str):
                custom.api_key = data['apiKey']
            if 'personality' in data and isinstance(data['personality'], str):
                defaults.personality = data['personality']
            if 'customPrompt' in data and isinstance(data['customPrompt'], str):
                defaults.custom_prompt = data['customPrompt']
            if 'birthday' in data and isinstance(data['birthday'], str):
                defaults.birthday = data['birthday']

            # Feishu voice sub-settings
            feishu_in = data.get('feishu')
            if isinstance(feishu_in, dict):
                if 'asrEnabled' in feishu_in and isinstance(feishu_in['asrEnabled'], bool):
                    feishu.asr_enabled = feishu_in['asrEnabled']
                if 'ttsEnabled' in feishu_in and isinstance(feishu_in['ttsEnabled'], bool):
                    feishu.tts_enabled = feishu_in['ttsEnabled']
                if 'ttsVoice' in feishu_in and isinstance(feishu_in['ttsVoice'], str):
                    feishu.tts_voice = feishu_in['ttsVoice']

            save_config(config)
            print(f"[API] Settings saved (model={defaults.model}, fast_model={defaults.fast_model}, personality={defaults.personality})")
            body = json.dumps({'success': True})
            response = self._http_response(200, body)
            writer.write(response.encode())
            await writer.drain()
        except Exception as e:
            print(f"[API] Error saving settings: {e}")
            import traceback
            traceback.print_exc()
            body = json.dumps({'success': False, 'error': str(e)})
            response = self._http_response(500, body)
            writer.write(response.encode())
            await writer.drain()

    async def _transcribe_audio(self, file_path: str) -> str | None:
        """Transcribe audio file using ASR file transcription API."""
        try:
            from desktopclaw.config import load_config
            config = load_config()
            
            if not config.channels.feishu.asr_enabled:
                return None
            
            api_key = config.channels.feishu.asr_api_key
            if not api_key:
                return None
            
            import dashscope
            import time
            
            dashscope.api_key = api_key
            
            print(f"[ASR] Processing file: {file_path}")
            
            # Use MultiModalConversation for ASR with local file
            try:
                from pathlib import Path
                
                # Convert webm to wav using pydub if available
                wav_path = Path(file_path).with_suffix('.wav')
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_file(file_path, format="webm")
                    audio = audio.set_frame_rate(16000).set_channels(1)
                    audio.export(wav_path, format="wav")
                    file_path = str(wav_path)
                    print(f"[ASR] Converted to wav: {file_path}")
                except Exception as e:
                    print(f"[ASR] pydub not available, using original file: {e}")
                
                # Use MultiModalConversation with local file
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"audio": file_path}
                        ]
                    }
                ]
                
                response = dashscope.MultiModalConversation.call(
                    model="qwen3-asr-flash",
                    messages=messages,
                    result_format="message",
                    asr_options={
                        "enable_lid": True,
                        "enable_itn": False
                    }
                )
                
                if response.status_code != 200:
                    print(f"[ASR] Failed: HTTP {response.status_code}, {response.message}")
                    return None
                
                response_data = response.output if hasattr(response, 'output') else {}
                if response_data and "choices" in response_data:
                    choices = response_data["choices"]
                    if choices and len(choices) > 0:
                        message_content = choices[0].get("message", {}).get("content", [])
                        for item in message_content:
                            if isinstance(item, dict) and "text" in item:
                                transcription = item["text"]
                                print(f"[ASR] Result: {transcription}")
                                # Clean up temp wav file
                                if wav_path.exists() and str(wav_path) != file_path:
                                    wav_path.unlink()
                                return transcription
                
                print(f"[ASR] Unexpected response format: {response_data}")
                return None
                
            except Exception as e:
                print(f"[ASR] Error: {e}")
                import traceback
                traceback.print_exc()
                return None
            
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _synthesize_speech(self, text: str) -> str | None:
        """Synthesize speech using DashScope TTS API. Returns the path to the generated audio file."""
        try:
            from desktopclaw.config import load_config
            config = load_config()

            if not config.channels.feishu.tts_enabled:
                return None

            api_key = config.channels.feishu.asr_api_key
            if not api_key:
                print("[TTS] No API key configured")
                return None

            import dashscope
            dashscope.api_key = api_key

            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            voice = config.channels.feishu.tts_voice or "Cherry"

            print(f"[TTS] Synthesizing with voice={voice}, text={text[:50]}...")

            response = dashscope.audio.qwen_tts.SpeechSynthesizer.call(
                model="qwen3-tts-flash",
                api_key=api_key,
                text=text,
                voice=voice,
            )

            if response.status_code == 200:
                audio_dir = get_media_dir("feishu")
                audio_dir.mkdir(parents=True, exist_ok=True)
                import uuid
                file_path = audio_dir / f"{uuid.uuid4().hex}.mp3"

                audio_url = None
                try:
                    resp_data = response
                    if isinstance(response, str):
                        import json as json_mod
                        resp_data = json_mod.loads(response)

                    if isinstance(resp_data, dict):
                        if "output" in resp_data and isinstance(resp_data["output"], dict):
                            audio_obj = resp_data["output"].get("audio", {})
                            if isinstance(audio_obj, dict):
                                audio_url = audio_obj.get("url") or audio_obj.get("data")
                except (KeyError, TypeError, AttributeError, json_mod.JSONDecodeError):
                    pass

                if not audio_url:
                    print(f"[TTS] No audio URL in response: {response}")
                    return None

                print(f"[TTS] Downloading from: {audio_url[:80]}...")
                try:
                    import urllib.request
                    with urllib.request.urlopen(audio_url, timeout=30) as remote:
                        audio_bytes = remote.read()
                except Exception as e:
                    print(f"[TTS] Download failed: {e}")
                    return None

                with open(file_path, "wb") as f:
                    f.write(audio_bytes)

                print(f"[TTS] Saved to: {file_path} ({len(audio_bytes)} bytes)")
                return f"http://127.0.0.1:{self.port}/media/{file_path.name}"
            else:
                print(f"[TTS] Failed: {response.code} {response.message}")
                return None

        except Exception as e:
            print(f"[TTS] Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _handle_feishu_sse(self, writer: asyncio.StreamWriter):
        """Handle SSE connection for Feishu event subscription."""
        print(f"[API] New Feishu SSE client connected")

        sse_headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n"
        )
        writer.write(sse_headers.encode())
        await writer.drain()

        async with self._feishu_sse_lock:
            self._feishu_sse_clients.append(writer)

        try:
            while True:
                await asyncio.sleep(30)
                heartbeat = f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                try:
                    writer.write(heartbeat.encode())
                    await writer.drain()
                except (ConnectionResetError, BrokenPipeError):
                    break
        except asyncio.CancelledError:
            pass
        finally:
            async with self._feishu_sse_lock:
                if writer in self._feishu_sse_clients:
                    self._feishu_sse_clients.remove(writer)
            print(f"[API] Feishu SSE client disconnected")

    async def broadcast_feishu_event(self, event_type: str, data: dict):
        """Broadcast a Feishu event to all connected SSE clients."""
        event = {
            'type': event_type,
            **data
        }
        event_data = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        async with self._feishu_sse_lock:
            print(f"[API] Broadcasting {event_type} to {len(self._feishu_sse_clients)} clients: {str(data)[:100]}")
            disconnected = []
            for client in self._feishu_sse_clients:
                try:
                    client.write(event_data.encode())
                    await client.drain()
                except (ConnectionResetError, BrokenPipeError) as e:
                    print(f"[API] Client write error: {e}")
                    disconnected.append(client)
            for client in disconnected:
                if client in self._feishu_sse_clients:
                    self._feishu_sse_clients.remove(client)

    def broadcast_feishu_inbound(self, msg):
        """Broadcast an inbound Feishu message (sync callback from channel)."""
        print(f"[API] broadcast_feishu_inbound called: {msg.content[:50]}...")
        asyncio.create_task(self._broadcast_feishu_inbound_async(msg))

    async def _broadcast_feishu_inbound_async(self, msg):
        """Async helper to broadcast inbound message."""
        try:
            print(f"[API] Broadcasting inbound to {len(self._feishu_sse_clients)} clients")
            print(f"[API] msg.media: {msg.media}")
            print(f"[API] msg.metadata: {msg.metadata}")
            event_data = {
                'content': msg.content,
                'sender_id': msg.sender_id,
                'chat_id': msg.chat_id,
            }
            if msg.media:
                event_data['media'] = msg.media
            if msg.metadata:
                event_data['metadata'] = msg.metadata
            print(f"[API] event_data: {event_data}")
            await self.broadcast_feishu_event('inbound', event_data)
        except Exception as e:
            print(f"[API] Error broadcasting feishu inbound: {e}")

    def broadcast_feishu_outbound(self, msg):
        """Broadcast an outbound Feishu message (sync callback from channel manager)."""
        print(f"[API] broadcast_feishu_outbound called: {msg.content[:50]}...")
        asyncio.create_task(self._broadcast_feishu_outbound_async(msg))

    async def _broadcast_feishu_outbound_async(self, msg):
        """Async helper to broadcast outbound message."""
        try:
            print(f"[API] Broadcasting outbound to {len(self._feishu_sse_clients)} clients")
            await self.broadcast_feishu_event('outbound', {
                'content': msg.content,
                'chat_id': msg.chat_id,
            })
        except Exception as e:
            print(f"[API] Error broadcasting feishu outbound: {e}")

    async def _handle_chat_request(self, reader, writer, headers):
        """Handle chat request with streaming tool call updates."""
        accept_header = headers.get('accept', '')
        wants_streaming = 'text/event-stream' in accept_header

        content_length = int(headers.get('content-length', 0))
        if content_length <= 0:
            error_body = json.dumps({'success': False, 'error': 'Empty body'})
            response = self._http_response(400, error_body)
            writer.write(response.encode())
            await writer.drain()
            return

        body = await asyncio.wait_for(reader.read(content_length), timeout=5.0)
        try:
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            error_body = json.dumps({'success': False, 'error': f'Invalid JSON: {str(e)}'})
            response = self._http_response(400, error_body)
            writer.write(response.encode())
            await writer.drain()
            return

        message = data.get('message', '')
        channel = data.get('channel', 'api')
        model_id = data.get('modelId')
        api_key = data.get('apiKey')
        api_base = data.get('baseUrl')
        personality = data.get('personality')
        custom_prompt = data.get('customPrompt')
        session_key = data.get('sessionKey') or f"api:frontend:{channel}"
        print(f"[API] Processing message: {message[:50]}... (channel={channel}, session={session_key}, model={model_id}, api_base={api_base})")

        if wants_streaming:
            await self._send_streaming_response(
                writer, message, channel, model_id, api_key, api_base, personality, custom_prompt, session_key,
            )
        else:
            await self._send_standard_response(
                writer, message, channel, model_id, api_key, api_base, personality, custom_prompt, session_key,
            )

    @staticmethod
    def _resolve_session_key(channel: str = 'api', session_key: str | None = None) -> str:
        if session_key:
            return session_key
        return f"api:frontend:{channel}"

    def _get_memory_embedder(self):
        try:
            services = getattr(self.agent, "_memory_services", None)
            if services is None:
                return None
            candidate = getattr(services, "embedder", None)
            if candidate is not None and hasattr(candidate, "get_load_status"):
                return candidate
        except Exception:
            pass
        return None

    def _get_memory_index_worker(self):
        try:
            services = getattr(self.agent, "_memory_services", None)
            if services is None:
                return None
            return getattr(services, "index_worker", None)
        except Exception:
            return None

    async def _handle_get_memory(self, writer) -> None:
        """Return user + strategy memory for frontend visualization."""
        try:
            config = load_config()
            embedder = self._get_memory_embedder()
            payload = build_memory_payload(
                config.workspace_path,
                embedder=embedder,
                memory_config=config.agents.memory,
            )
            body = json.dumps(payload, ensure_ascii=False)
            response = self._http_response(200, body)
            writer.write(response.encode())
            await writer.drain()
        except Exception as e:
            print(f"[API] Error reading memory: {e}")
            body = json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
            response = self._http_response(500, body)
            writer.write(response.encode())
            await writer.drain()

    async def _handle_retry_embedding(self, writer) -> None:
        """Retry/resume embedding model download and re-queue failed strategy indexes."""
        embedder = self._get_memory_embedder()
        if embedder is None:
            body = json.dumps({"success": False, "error": "Memory or embedder disabled"}, ensure_ascii=False)
            response = self._http_response(400, body)
            writer.write(response.encode())
            await writer.drain()
            return
        try:
            embedder._available = None
            ok = await embedder.preload()
            worker = self._get_memory_index_worker()
            if ok and worker is not None:
                await worker.recover_failed_after_embedder_ready()
            snap = embedder.get_load_status()
            body = json.dumps({"success": ok, "embeddingModel": {
                "status": snap["status"],
                "progress": snap["progress"],
                "model": snap["model"],
                "message": snap["message"],
                "error": snap.get("error", ""),
                "resumed": snap.get("resumed", False),
            }}, ensure_ascii=False)
            response = self._http_response(200 if ok else 500, body)
            writer.write(response.encode())
            await writer.drain()
        except Exception as e:
            print(f"[API] Error retrying embedding download: {e}")
            body = json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
            response = self._http_response(500, body)
            writer.write(response.encode())
            await writer.drain()

    async def _handle_list_sessions(self, writer) -> None:
        """List frontend sessions for history import."""
        prefix = "api:frontend"
        sessions_out: list[dict[str, Any]] = []
        for info in self.agent.sessions.list_sessions():
            key = info.get("key", "")
            if not key.startswith(prefix):
                continue
            session = self.agent.sessions.get_or_create(key)
            sessions_out.append(session_info_dict(session))
        body = json.dumps({"success": True, "sessions": sessions_out}, ensure_ascii=False)
        response = self._http_response(200, body)
        writer.write(response.encode())
        await writer.drain()

    async def _handle_get_session_messages(self, writer, session_key: str) -> None:
        """Return UI-friendly messages for a session key."""
        if not session_key.startswith("api:frontend"):
            body = json.dumps({"success": False, "error": "Forbidden session key"}, ensure_ascii=False)
            response = self._http_response(403, body)
            writer.write(response.encode())
            await writer.drain()
            return

        session = self.agent.sessions.get_or_create(session_key)
        messages = session_messages_for_ui(session)
        body = json.dumps(
            {
                "success": True,
                "key": session_key,
                "messages": messages,
                "updated_at": session.updated_at.isoformat(),
            },
            ensure_ascii=False,
        )
        response = self._http_response(200, body)
        writer.write(response.encode())
        await writer.drain()

    async def _handle_delete_session(self, writer, session_key: str) -> None:
        """Delete a frontend session and its persisted history."""
        if not session_key.startswith("api:frontend"):
            body = json.dumps({"success": False, "error": "Forbidden session key"}, ensure_ascii=False)
            response = self._http_response(403, body)
            writer.write(response.encode())
            await writer.drain()
            return

        deleted = self.agent.sessions.delete(session_key)
        if not deleted:
            body = json.dumps({"success": False, "error": "Session not found"}, ensure_ascii=False)
            response = self._http_response(404, body)
            writer.write(response.encode())
            await writer.drain()
            return

        body = json.dumps({"success": True}, ensure_ascii=False)
        response = self._http_response(200, body)
        writer.write(response.encode())
        await writer.drain()

    async def _send_streaming_response(
        self, writer, message, channel='api', model_id=None, api_key=None, api_base=None,
        personality=None, custom_prompt=None, session_key: str | None = None,
    ):
        """Send streaming response with tool call updates via SSE."""
        print(f"[API] Streaming response started for: {message[:50]}... (channel={channel}, model={model_id})")

        # Send SSE headers
        sse_headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n"
        )
        writer.write(sse_headers.encode())
        await writer.drain()

        # Send initial thinking event
        thinking_event = {'type': 'thinking', 'content': 'AI 正在思考...'}
        writer.write(f"data: {json.dumps(thinking_event, ensure_ascii=False)}\n\n".encode())
        await writer.drain()

        # Create event for completion
        response_received = asyncio.Event()
        final_response = [None]

        async def collect_progress(content: str, *, tool_hint: bool = False) -> None:
            """Collect tool calls and send SSE events."""
            event_type = 'tool_call' if tool_hint else 'progress'
            event = {
                'type': event_type,
                'content': content
            }
            event_data = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            try:
                writer.write(event_data.encode())
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                pass

        async def process_with_agent():
            """Process message through agent."""
            try:
                resolved_key = self._resolve_session_key(channel, session_key)
                response = await self.agent.process_direct(
                    message,
                    session_key=resolved_key,
                    channel=channel,
                    chat_id="frontend",
                    on_progress=collect_progress,
                    model=model_id,
                    api_key=api_key,
                    api_base=api_base,
                    personality=personality,
                    custom_prompt=custom_prompt
                )
                final_response[0] = response
                response_received.set()
            except Exception as e:
                final_response[0] = f"Error: {str(e)}"
                response_received.set()

        # Start agent processing
        asyncio.create_task(process_with_agent())

        # Wait for response with timeout
        try:
            await asyncio.wait_for(response_received.wait(), timeout=600.0)
        except asyncio.TimeoutError:
            final_response[0] = "请求超时，请稍后重试。(请求处理时间超过10分钟)"

        # Send final response event
        final_event = self._build_complete_event(final_response[0])
        event_data = f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"
        try:
            writer.write(event_data.encode())
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass

        print(f"[API] Streaming response completed")

    async def _send_standard_response(
        self, writer, message, channel='api', model_id=None, api_key=None, api_base=None,
        personality=None, custom_prompt=None, session_key: str | None = None,
    ):
        """Send non-streaming standard response."""
        try:
            response = await self.process_message(
                message, channel, model_id, api_key, api_base, personality, custom_prompt, session_key,
            )
            result = {
                'success': True,
                'response': response.content,
                'usage': response.usage or empty_usage_dict(),
            }
            response_body = json.dumps(result, ensure_ascii=False)
            print(f"[API] Response sent successful"  )
        except Exception as e:
            print(f"[API] Error processing message: {e}")
            result = {'success': False, 'error': str(e)}
            response_body = json.dumps(result, ensure_ascii=False)

        response = self._http_response(200, response_body)
        writer.write(response.encode())
        await writer.drain()

    def _http_response(self, status_code: int, body: str) -> str:
        """Generate HTTP response."""
        status_text = {200: 'OK', 404: 'Not Found', 500: 'Internal Server Error'}.get(status_code, 'Unknown')
        return (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body.encode('utf-8'))}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            f"Access-Control-Allow-Headers: Content-Type, Authorization, Accept\r\n"
            f"\r\n"
            f"{body}"
        )

    def _cors_response(self, status_code: int) -> str:
        """Generate CORS preflight response."""
        return (
            f"HTTP/1.1 {status_code} OK\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            f"Access-Control-Allow-Headers: Content-Type, Authorization, Accept\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )

    async def start(self):
        """Start the API server."""
        self.server = await asyncio.start_server(
            self.handle_request, '127.0.0.1', self.port
        )
        print(f"API Server started on http://127.0.0.1:{self.port}")

    async def stop(self):
        """Stop the API server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        print("API Server stopped")

    async def process_message(
        self, message: str, channel: str = 'api', model_id=None, api_key=None, api_base=None,
        personality=None, custom_prompt=None, session_key: str | None = None,
    ) -> ProcessResult:
        """Process a message through the agent and return the response."""
        response_future = asyncio.Future()
        resolved_key = self._resolve_session_key(channel, session_key)

        async def handle_response():
            try:
                response = await self.agent.process_direct(
                    message,
                    session_key=resolved_key,
                    channel=channel,
                    chat_id="frontend",
                    model=model_id,
                    api_key=api_key,
                    api_base=api_base,
                    personality=personality,
                    custom_prompt=custom_prompt
                )
                if not response_future.done():
                    response_future.set_result(response)
            except Exception as e:
                if not response_future.done():
                    response_future.set_exception(e)

        asyncio.create_task(handle_response())

        try:
            response = await asyncio.wait_for(response_future, timeout=600.0)
            return response
        except asyncio.TimeoutError:
            return ProcessResult(
                content="请求超时，请稍后重试。(请求处理时间超过10分钟)",
                usage=empty_usage_dict(),
            )


async def start_api_server(agent, bus, port: int = 3000, channel_manager=None):
    """Start the API server with the given agent and message bus."""
    server = APIServer(agent, bus, port)
    if channel_manager:
        channel_manager.set_inbound_callback(server.broadcast_feishu_inbound)
    await server.start()
    return server
