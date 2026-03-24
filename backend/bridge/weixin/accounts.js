import fs from "node:fs";
import path from "node:path";
import os from "node:os";

export const DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com";
export const CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c";

function resolveStateDir() {
  return process.env.NANOBOT_STATE_DIR
    ? path.resolve(process.env.NANOBOT_STATE_DIR)
    : path.join(os.homedir(), ".nanobot");
}

function resolveWeixinStateDir() {
  return path.join(resolveStateDir(), "weixin");
}

function resolveAccountsDir() {
  return path.join(resolveWeixinStateDir(), "accounts");
}

function resolveAccountIndexPath() {
  return path.join(resolveWeixinStateDir(), "accounts.json");
}

function resolveAccountPath(accountId) {
  return path.join(resolveAccountsDir(), `${accountId}.json`);
}

export function resolveSyncBufPath(accountId) {
  return path.join(resolveAccountsDir(), `${accountId}.sync.json`);
}

export function listAccountIds() {
  const filePath = resolveAccountIndexPath();
  try {
    if (!fs.existsSync(filePath)) return [];
    const raw = fs.readFileSync(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((id) => typeof id === "string" && id.trim() !== "");
  } catch {
    return [];
  }
}

export function registerAccountId(accountId) {
  const dir = resolveWeixinStateDir();
  fs.mkdirSync(dir, { recursive: true });
  const existing = listAccountIds();
  if (existing.includes(accountId)) return;
  const updated = [...existing, accountId];
  fs.writeFileSync(resolveAccountIndexPath(), JSON.stringify(updated, null, 2), "utf-8");
}

export function loadAccount(accountId) {
  try {
    const filePath = resolveAccountPath(accountId);
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

export function saveAccount(accountId, update) {
  const dir = resolveAccountsDir();
  fs.mkdirSync(dir, { recursive: true });

  const existing = loadAccount(accountId) ?? {};
  const token = update.token?.trim() || existing.token;
  const baseUrl = update.baseUrl?.trim() || existing.baseUrl;
  const userId = update.userId !== undefined
    ? (update.userId.trim() || undefined)
    : (existing.userId?.trim() || undefined);

  const data = {
    ...(token ? { token, savedAt: new Date().toISOString() } : {}),
    ...(baseUrl ? { baseUrl } : {}),
    ...(userId ? { userId } : {}),
  };

  const filePath = resolveAccountPath(accountId);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
}

export function loadSyncBuf(accountId) {
  try {
    const filePath = resolveSyncBufPath(accountId);
    if (!fs.existsSync(filePath)) return "";
    const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    return data.get_updates_buf ?? "";
  } catch {
    return "";
  }
}

export function saveSyncBuf(accountId, buf) {
  const dir = resolveAccountsDir();
  fs.mkdirSync(dir, { recursive: true });
  const filePath = resolveSyncBufPath(accountId);
  fs.writeFileSync(filePath, JSON.stringify({ get_updates_buf: buf }), "utf-8");
}
