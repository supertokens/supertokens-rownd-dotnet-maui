#!/usr/bin/env python3
"""Generate a disposable observation overlay of the pinned shared Android harness."""
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def transform(source):
    def replace(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError('Pinned harness source shape changed; review the overlay')
        source = source.replace(old, new)

    replace('import { generateKeyPairSync }', 'import { createHash, generateKeyPairSync }')
    replace('type MagicLinkCapture = {', '''const fingerprint = (value: string) => createHash("sha256").update(value).digest("hex");
const consumeObservations: { challenge: string; status: string; userId?: string }[] = [];

type MagicLinkCapture = {
  capturedAt?: number;''')
    # Delivery remains the existing email/SMS capture implementation.
    source = source.replace('urlWithLinkCode: input.urlWithLinkCode,',
                            'capturedAt: Date.now(),\n                urlWithLinkCode: input.urlWithLinkCode,')
    replace('function resetState(namespace?: string) {',
            'function resetState(namespace?: string) {\n  consumeObservations.length = 0;')
    replace('state.counters.passwordlessConsume += 1;', '''state.counters.passwordlessConsume += 1;
      const originalJson = res.json.bind(res);
      res.json = (body: any) => {
        consumeObservations.push({
          challenge: fingerprint(String(req.body?.preAuthSessionId || "")),
          status: String(body?.status || "UNKNOWN"),
          userId: body?.status === "OK" ? body.user?.id : undefined,
        });
        return originalJson(body);
      };''')
    replace('  app.get("/test/passwordless/consumes",', '''  app.get("/test/m4/observations", (_req, res) => {
    res.json({ consumes: consumeObservations });
  });

  app.get("/test/passwordless/consumes",''')
    replace('''  app.get("/test/protected", verifySession({ checkDatabase: true }) as any, async (req: any, res) => {
    res.json({
      userId: req.session.getUserId(),
      accessTokenPayload: req.session.getAccessTokenPayload(),''', '''  app.get("/test/protected", verifySession({ checkDatabase: true }) as any, async (req: any, res) => {
    res.json({
      userId: req.session.getUserId(),
      sessionFingerprint: fingerprint(req.session.getHandle()),''')
    return source


def main():
    pins = json.loads((ROOT / 'eng/versions.json').read_text())['nativeSources']['android']
    sibling = ROOT.parent / pins['directory']
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=sibling, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', 'test-server'], cwd=sibling, text=True)
    if revision != pins['commit'] or dirty:
        raise SystemExit('Pinned, clean Android test-server required')
    output = ROOT / 'artifacts/m4-harness'
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(sibling / 'test-server', output / 'test-server', dirs_exist_ok=True)
    source = sibling / 'test-server/server.ts'
    (output / 'test-server/server.ts').write_text(transform(source.read_text()))
    (output / 'package.json').write_text('{"type":"module"}\n')
    modules = output / 'node_modules'
    if not modules.is_symlink() and not modules.exists():
        modules.symlink_to(sibling / 'node_modules', target_is_directory=True)
    print('Prepared artifacts/m4-harness; no server or containers started')


if __name__ == '__main__':
    main()
