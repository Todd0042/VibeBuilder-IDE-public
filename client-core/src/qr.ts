// Pairing QR payload parser for the JSON emitted by `vibebuilder pair`: {"vb":1,"u":"<url>","c":"<code>"}.

export interface PairingQr {
  server: string;
  code: string;
}

export function parsePairingQr(raw: string): PairingQr | null {
  try {
    const obj = JSON.parse(raw);
    if (obj && obj.vb === 1 && typeof obj.u === "string" && typeof obj.c === "string") {
      const server = obj.u.trim();
      const code = obj.c.toUpperCase().replace(/[^A-Z0-9]/g, "");
      if (server && code.length === 6) {
        return { server, code: `${code.slice(0, 3)}-${code.slice(3)}` };
      }
    }
  } catch {
    /* ignore non-JSON payloads */
  }
  return null;
}
