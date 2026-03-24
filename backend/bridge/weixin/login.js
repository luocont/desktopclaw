import { fetchQRCode, pollQRStatus } from "./api.js";
import { saveAccount, registerAccountId, DEFAULT_BASE_URL } from "./accounts.js";

const MAX_QR_REFRESH_COUNT = 3;

export async function doQRLogin(opts = {}) {
  const apiBaseUrl = opts.apiBaseUrl ?? DEFAULT_BASE_URL;
  const botType = opts.botType ?? "3";
  const verbose = opts.verbose ?? true;

  console.log("[Weixin] Fetching QR code...");
  let qrData = await fetchQRCode(apiBaseUrl, botType);
  let qrcode = qrData.qrcode;
  let qrcodeUrl = qrData.qrcode_img_content;

  console.log(`[Weixin] QR code URL: ${qrcodeUrl}`);

  try {
    const qrterm = await import("qrcode-terminal");
    qrterm.default.generate(qrcodeUrl, { small: true });
  } catch {
    console.log("[Weixin] qrcode-terminal not available, use URL above");
  }

  console.log("[Weixin] Waiting for scan...");

  let qrRefreshCount = 1;
  let scannedPrinted = false;
  const deadline = Date.now() + (opts.timeoutMs ?? 480_000);

  while (Date.now() < deadline) {
    const status = await pollQRStatus(apiBaseUrl, qrcode);

    switch (status.status) {
      case "wait":
        if (verbose) process.stdout.write(".");
        break;

      case "scaned":
        if (!scannedPrinted) {
          process.stdout.write("\n👀 Scanned! Confirm in WeChat...\n");
          scannedPrinted = true;
        }
        break;

      case "expired":
        qrRefreshCount++;
        if (qrRefreshCount > MAX_QR_REFRESH_COUNT) {
          throw new Error("QR code expired too many times, please retry");
        }
        process.stdout.write(`\n⏳ QR expired, refreshing (${qrRefreshCount}/${MAX_QR_REFRESH_COUNT})...\n`);
        qrData = await fetchQRCode(apiBaseUrl, botType);
        qrcode = qrData.qrcode;
        qrcodeUrl = qrData.qrcode_img_content;
        scannedPrinted = false;
        console.log(`[Weixin] New QR URL: ${qrcodeUrl}`);
        try {
          const qrterm = await import("qrcode-terminal");
          qrterm.default.generate(qrcodeUrl, { small: true });
        } catch {
          console.log("[Weixin] Use URL above to scan");
        }
        break;

      case "confirmed": {
        if (!status.ilink_bot_id) {
          throw new Error("Login confirmed but ilink_bot_id missing");
        }
        const accountId = status.ilink_bot_id;
        saveAccount(accountId, {
          token: status.bot_token,
          baseUrl: status.baseurl || apiBaseUrl,
          userId: status.ilink_user_id,
        });
        registerAccountId(accountId);
        process.stdout.write("\n✅ WeChat connected!\n");
        console.log(`[Weixin] Account ID: ${accountId}`);
        console.log(`[Weixin] User ID: ${status.ilink_user_id}`);
        return {
          accountId,
          token: status.bot_token,
          baseUrl: status.baseurl || apiBaseUrl,
          userId: status.ilink_user_id,
        };
      }
    }

    await new Promise((r) => setTimeout(r, 1000));
  }

  throw new Error("Login timed out");
}
