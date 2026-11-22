/** Contract that each host platform (`desktop` / `mobile`) implements via the `@platform` alias. */
export interface PlatformBridge {
  readonly canTunnel: boolean;
  readonly canAdb: boolean;
  readonly canGui: boolean;
  readonly canQrScan: boolean;
  tokenGet(server: string): Promise<string | null>;
  tokenSet(server: string, token: string): Promise<void>;
  tokenDelete(server: string): Promise<void>;
  deviceName(): Promise<string>;
  onWindowClose(handler: () => Promise<boolean>): Promise<void>;
  closeWindow(): Promise<void>;
  setZoom(factor: number): Promise<void>;
  tunnelSession(server: string, session: string | null): Promise<void>;
  portForward(remote: number, local: number): Promise<number>;
  portUnforward(remote: number): Promise<void>;
  portForwards(): Promise<[number, number][]>;
  adbConnect(): Promise<void>;
  adbDisconnect(): Promise<void>;
  adbStatus(): Promise<boolean>;
  guiStart(runId: string): Promise<string>;
  guiStop(runId: string): Promise<void>;
  scanPairingQr?: () => Promise<{ server: string; code: string } | null>;
  openExternal?: (url: string) => Promise<void>;
  setKeepAwake?: (active: boolean) => Promise<void>;
  onAppLifecycle?: (hooks: { onBackground?: () => void; onResume?: () => void }) => () => void;
}
