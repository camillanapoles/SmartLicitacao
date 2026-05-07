/**
 * @jest-environment node
 *
 * STORY-SEO-027: exact orphan root /contratos/orgao must return 410 without
 * affecting the dynamic /contratos/orgao/[cnpj] route.
 */

import fs from 'fs';
import path from 'path';

const middlewarePath = path.join(__dirname, '..', 'middleware.ts');

describe('STORY-SEO-027 middleware 410 guard', () => {
  it('uses an exact pathname match for /contratos/orgao', () => {
    const source = fs.readFileSync(middlewarePath, 'utf-8');

    expect(source).toContain('pathname === "/contratos/orgao"');
    expect(source).not.toContain('pathname.startsWith("/contratos/orgao")');
  });

  it('returns HTTP 410 Gone for the exact orphan root', () => {
    const source = fs.readFileSync(middlewarePath, 'utf-8');

    expect(source).toContain('new NextResponse("Gone", { status: 410 })');
  });
});
