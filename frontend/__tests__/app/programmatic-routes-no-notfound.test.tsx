/**
 * ADR-SEO-001 compliance test — programmatic SEO routes must not call
 * notFound() on data gaps. This test mirrors the CI gate logic in
 * .github/workflows/audit-seo-notfound.yml so violations are caught
 * locally before push.
 *
 * Rules:
 * - notFound() calls in code lines are allowed only if the same line OR the
 *   immediately preceding line contains `adr-seo-001-allow:`.
 * - Pure comment lines (trimmed starts with //, /*, or *) are exempt.
 * - Routes that received EmptyStateSEO replacements must not import notFound
 *   unless they also have format-guard calls marked with adr-seo-001-allow.
 */

import * as fs from 'fs';
import * as path from 'path';

const FRONTEND_ROOT = path.resolve(__dirname, '../../');

const PROTECTED_PREFIXES = [
  'app/observatorio',
  'app/cnpj',
  'app/fornecedores',
  'app/orgaos',
  'app/municipios',
  'app/licitacoes',
  'app/contratos',
  'app/alertas-publicos',
  'app/itens',
  'app/blog',
  'app/casos',
  'app/glossario',
  'app/guia',
  'app/masterclass',
  'app/perguntas',
  'app/compliance',
];

function collectFilesRecursive(dir: string, exts: string[]): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectFilesRecursive(fullPath, exts));
    } else if (exts.some((ext) => entry.name.endsWith(ext))) {
      results.push(fullPath);
    }
  }
  return results;
}

function collectFiles(): string[] {
  const results: string[] = [];
  for (const prefix of PROTECTED_PREFIXES) {
    const dir = path.join(FRONTEND_ROOT, prefix);
    results.push(...collectFilesRecursive(dir, ['.ts', '.tsx']));
  }
  return results;
}

function isCommentLine(line: string): boolean {
  const trimmed = line.trimStart();
  return (
    trimmed.startsWith('//') ||
    trimmed.startsWith('/*') ||
    trimmed.startsWith('*')
  );
}

interface Violation {
  file: string;
  line: number;
  content: string;
}

function scanFile(filePath: string): Violation[] {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');
  const violations: Violation[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.match(/notFound\s*\(/)) continue;

    // Skip comment-only lines
    if (isCommentLine(line)) continue;

    // Same-line allow marker?
    if (line.includes('adr-seo-001-allow:')) continue;

    // Preceding-line allow marker?
    if (i > 0 && lines[i - 1].includes('adr-seo-001-allow:')) continue;

    violations.push({
      file: path.relative(FRONTEND_ROOT, filePath),
      line: i + 1,
      content: line,
    });
  }
  return violations;
}

describe('ADR-SEO-001: No unmarked notFound() in programmatic SEO routes', () => {
  const files = collectFiles();

  test('should find at least one protected route file to scan', () => {
    expect(files.length).toBeGreaterThan(0);
  });

  test('all notFound() calls in protected routes carry adr-seo-001-allow marker', () => {
    const allViolations: Violation[] = [];

    for (const file of files) {
      const violations = scanFile(file);
      allViolations.push(...violations);
    }

    if (allViolations.length > 0) {
      const details = allViolations
        .map((v) => `  ${v.file}:${v.line}: ${v.content.trim()}`)
        .join('\n');
      fail(
        `Found ${allViolations.length} unmarked notFound() call(s) in protected SEO routes.\n` +
          `Add "// adr-seo-001-allow: <reason>" on the same line or preceding line.\n\n` +
          `Violations:\n${details}`
      );
    }

    expect(allViolations).toHaveLength(0);
  });

  test('data-absence routes render EmptyStateSEO instead of calling notFound()', () => {
    // Spot-check: routes that fetch backend data must NOT have bare notFound()
    // for the data-absence case. We verify the key routes have EmptyStateSEO import.
    const dataAbsenceRoutes = [
      'app/cnpj/[cnpj]/page.tsx',
      'app/fornecedores/[cnpj]/page.tsx',
      'app/orgaos/[slug]/page.tsx',
      'app/municipios/[slug]/page.tsx',
      'app/contratos/orgao/[cnpj]/page.tsx',
      'app/itens/[catmat]/page.tsx',
      'app/compliance/[cnpj]/page.tsx',
    ];

    for (const route of dataAbsenceRoutes) {
      const filePath = path.join(FRONTEND_ROOT, route);
      if (!fs.existsSync(filePath)) continue;

      const content = fs.readFileSync(filePath, 'utf-8');
      expect(content).toContain('EmptyStateSEO');
    }
  });
});
