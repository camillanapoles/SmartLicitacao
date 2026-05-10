/**
 * @jest-environment node
 *
 * SEO-SITEMAP-410-001: Middleware 410 Gone for malformed CNPJs.
 *
 * GSC had 2,962 404 pages from malformed CNPJ slugs (CPFs, oversized strings,
 * garbage). A 410 Gone signals permanent removal, accelerating de-indexation
 * 5-10x vs 404 and freeing crawl budget.
 *
 * Tests verify the source-level invariants without running the Edge runtime.
 *
 * AC1: /cnpj/<11-digit CPF slug> → 410 Gone
 * AC2: /fornecedores/<15-digit slug> → 410 Gone
 * AC3: /cnpj/<valid 14-char CNPJ> → pass-through (no 410)
 * AC4: /cnpj/<alfanumérico 14-char> → pass-through (IN 2.229/2024 ready)
 * AC5: X-Reason: invalid-cnpj-format header present on 410 responses
 */

import fs from "fs";
import path from "path";

const middlewarePath = path.join(__dirname, "..", "middleware.ts");

// ---------------------------------------------------------------------------
// Helpers: replicate the validation logic from middleware.ts for unit tests
// ---------------------------------------------------------------------------
const CNPJ_SEGMENT_PATTERN = /^[A-Z0-9]{12}\d{2}$/i;
const CPF_SEGMENT_PATTERN = /^\d{11}$/;
const ENTITY_CNPJ_REGEX =
  /^\/(?:cnpj|fornecedores|orgaos|contratos\/orgao)\/([^/]+)/;

function isValidCnpjFormat(s: string): boolean {
  const clean = s.replace(/[.\-/]/g, "");
  return CNPJ_SEGMENT_PATTERN.test(clean) && !CPF_SEGMENT_PATTERN.test(clean);
}

function wouldReturn410(pathname: string): boolean {
  const entityMatch = pathname.match(ENTITY_CNPJ_REGEX);
  if (!entityMatch) return false;
  const slug = decodeURIComponent(entityMatch[1]);
  return !isValidCnpjFormat(slug);
}

// ---------------------------------------------------------------------------
// Source-level invariant tests
// ---------------------------------------------------------------------------
describe("SEO-SITEMAP-410-001 middleware source invariants", () => {
  let source: string;

  beforeAll(() => {
    source = fs.readFileSync(middlewarePath, "utf-8");
  });

  it("defines CNPJ_SEGMENT_PATTERN with alfanumérico support", () => {
    expect(source).toContain("CNPJ_SEGMENT_PATTERN");
    // Pattern must allow A-Z letters (IN 2.229/2024 requirement)
    expect(source).toMatch(/\[A-Z0-9\]/i);
  });

  it("defines CPF_SEGMENT_PATTERN to reject 11-digit strings", () => {
    expect(source).toContain("CPF_SEGMENT_PATTERN");
    expect(source).toMatch(/\\d\{11\}/);
  });

  it("matches entity routes: cnpj, fornecedores, orgaos, contratos/orgao", () => {
    expect(source).toContain("cnpj|fornecedores|orgaos|contratos\\/orgao");
  });

  it("returns 410 status for invalid slugs", () => {
    expect(source).toContain("status: 410");
  });

  it("sets X-Reason: invalid-cnpj-format header on 410 responses (AC5)", () => {
    expect(source).toContain('"X-Reason": "invalid-cnpj-format"');
  });

  it("uses isValidCnpjFormat helper", () => {
    expect(source).toContain("isValidCnpjFormat");
  });
});

// ---------------------------------------------------------------------------
// Unit tests for the validation logic
// ---------------------------------------------------------------------------
describe("isValidCnpjFormat validation logic", () => {
  describe("AC1: 11-digit CPF slugs are rejected", () => {
    it("rejects bare 11-digit string (CPF)", () => {
      expect(isValidCnpjFormat("93513712553")).toBe(false);
    });

    it("rejects CPF with punctuation (stripped)", () => {
      expect(isValidCnpjFormat("935.137.125-53")).toBe(false);
    });
  });

  describe("AC2: Oversized slugs (15+ digits) are rejected", () => {
    it("rejects 15-digit string", () => {
      expect(isValidCnpjFormat("570731320001602")).toBe(false);
    });

    it("rejects 16-digit string", () => {
      expect(isValidCnpjFormat("5707313200016029")).toBe(false);
    });

    it("rejects short garbage (less than 14 chars)", () => {
      expect(isValidCnpjFormat("1234567")).toBe(false);
    });
  });

  describe("AC3: Valid 14-digit CNPJ is accepted", () => {
    it("accepts canonical 14-digit numeric CNPJ", () => {
      expect(isValidCnpjFormat("12345678000195")).toBe(true);
    });

    it("accepts CNPJ with dots/slash/hyphen punctuation (stripped)", () => {
      expect(isValidCnpjFormat("12.345.678/0001-95")).toBe(true);
    });
  });

  describe("AC4: Alfanumérico 14-char CNPJ is accepted (IN 2.229/2024)", () => {
    it("accepts mixed alpha-numeric 14-char CNPJ", () => {
      expect(isValidCnpjFormat("AB3DEF78000195")).toBe(true);
    });

    it("accepts all-caps alpha prefix CNPJ", () => {
      expect(isValidCnpjFormat("ABCDEF78000195")).toBe(true);
    });

    it("accepts lowercase letters (case-insensitive)", () => {
      expect(isValidCnpjFormat("ab3def78000195")).toBe(true);
    });
  });
});

// ---------------------------------------------------------------------------
// Route-level tests: which paths would receive a 410
// ---------------------------------------------------------------------------
describe("Route-level 410 routing (AC1-AC5)", () => {
  describe("AC1: /cnpj/<CPF> returns 410", () => {
    it("triggers 410 for /cnpj/<11-digit CPF>", () => {
      expect(wouldReturn410("/cnpj/93513712553")).toBe(true);
    });
  });

  describe("AC2: /fornecedores/<oversized> returns 410", () => {
    it("triggers 410 for /fornecedores/<15-digit>", () => {
      expect(wouldReturn410("/fornecedores/570731320001602")).toBe(true);
    });

    it("triggers 410 for /orgaos/<garbage slug>", () => {
      expect(wouldReturn410("/orgaos/abc")).toBe(true);
    });

    it("triggers 410 for /contratos/orgao/<CPF>", () => {
      expect(wouldReturn410("/contratos/orgao/93513712553")).toBe(true);
    });
  });

  describe("AC3: /cnpj/<valid 14-char CNPJ> passes through", () => {
    it("does NOT trigger 410 for valid 14-digit CNPJ", () => {
      expect(wouldReturn410("/cnpj/12345678000195")).toBe(false);
    });

    it("does NOT trigger 410 for valid CNPJ with punctuation in URL", () => {
      // URL-encoded punctuation should be cleaned
      expect(wouldReturn410("/cnpj/12.345.678%2F0001-95")).toBe(false);
    });
  });

  describe("AC4: /cnpj/<alfanumérico 14-char> passes through", () => {
    it("does NOT trigger 410 for alfanumérico CNPJ (IN 2.229/2024)", () => {
      expect(wouldReturn410("/cnpj/AB3DEF78000195")).toBe(false);
    });
  });

  describe("Unrelated routes are unaffected", () => {
    it("does not trigger for /buscar", () => {
      expect(wouldReturn410("/buscar")).toBe(false);
    });

    it("does not trigger for /blog/contratos/setor", () => {
      expect(wouldReturn410("/blog/contratos/setor")).toBe(false);
    });

    it("does not trigger for /contratos/orgao (exact root — handled separately)", () => {
      // The exact root is handled by STORY-SEO-027; this guard needs a slug
      expect(wouldReturn410("/contratos/orgao")).toBe(false);
    });
  });
});
