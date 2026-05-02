/**
 * STORY-SEO-026: robots.txt prefix-match fix for /alertas-publicos
 *
 * Validates RFC 9309 §2.2.2 longest-match semantics so that:
 * - /alertas (private logged-in panel) stays BLOCKED
 * - /alertas-publicos/* (public SEO pages) are ALLOWED
 *
 * Reference: https://www.rfc-editor.org/rfc/rfc9309#name-the-allow-and-disallow-line
 */

import * as fs from "fs";
import * as path from "path";

// ---------------------------------------------------------------------------
// Minimal RFC 9309 parser (User-agent: * block only)
// ---------------------------------------------------------------------------

type Rule = { allow: boolean; path: string };

function parseRobotsForUserAgentStar(content: string): Rule[] {
  const lines = content.split("\n").map((l) => l.trim());
  const rules: Rule[] = [];
  let inStarBlock = false;

  for (const line of lines) {
    if (line.startsWith("#") || line === "") continue;

    if (line.toLowerCase().startsWith("user-agent:")) {
      const ua = line.split(":")[1].trim();
      inStarBlock = ua === "*";
      continue;
    }

    if (!inStarBlock) continue;

    if (line.toLowerCase().startsWith("allow:")) {
      rules.push({ allow: true, path: line.split(":")[1].trim() });
    } else if (line.toLowerCase().startsWith("disallow:")) {
      rules.push({ allow: false, path: line.split(":")[1].trim() });
    }
  }

  return rules;
}

/**
 * RFC 9309 §2.2.2: longest matching path wins; on tie Allow wins.
 * Returns true if the path is allowed.
 */
function isAllowed(rules: Rule[], urlPath: string): boolean {
  let bestMatchLen = -1;
  let bestMatchAllow = true; // default allow

  for (const rule of rules) {
    const rp = rule.path;
    if (rp === "" || rp === "/") {
      if (rp === "/") {
        if (rp.length > bestMatchLen || (rp.length === bestMatchLen && rule.allow)) {
          bestMatchLen = rp.length;
          bestMatchAllow = rule.allow;
        }
      }
      continue;
    }
    if (urlPath.startsWith(rp)) {
      if (rp.length > bestMatchLen || (rp.length === bestMatchLen && rule.allow)) {
        bestMatchLen = rp.length;
        bestMatchAllow = rule.allow;
      }
    }
  }

  return bestMatchAllow;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("robots.txt — SEO-026 prefix-match fix", () => {
  let rules: Rule[];

  beforeAll(() => {
    const robotsPath = path.join(__dirname, "../../public/robots.txt");
    const content = fs.readFileSync(robotsPath, "utf8");
    rules = parseRobotsForUserAgentStar(content);
  });

  describe("private routes remain BLOCKED", () => {
    const privateRoutes = [
      "/alertas",
      "/admin",
      "/api/anything",
      "/dashboard",
      "/conta",
      "/buscar",
      "/pipeline",
      "/historico",
      "/mensagens",
      "/onboarding",
      "/recuperar-senha",
      "/redefinir-senha",
      "/auth/callback",
    ];

    it.each(privateRoutes)("%s is blocked", (route) => {
      expect(isAllowed(rules, route)).toBe(false);
    });
  });

  describe("public SEO routes are ALLOWED — SEO-026 fix", () => {
    const publicSeoRoutes = [
      "/alertas-publicos",
      "/alertas-publicos/saude/sp",
      "/alertas-publicos/materiais_eletricos/ac",
      "/alertas-publicos/materiais_eletricos/rr",
      "/alertas-publicos/materiais_eletricos/ba",
      "/alertas-publicos/materiais_eletricos/am",
      "/alertas-publicos/materiais_eletricos/pe",
    ];

    it.each(publicSeoRoutes)("%s is allowed (was blocked before SEO-026)", (route) => {
      expect(isAllowed(rules, route)).toBe(true);
    });
  });

  describe("other public pages remain ALLOWED", () => {
    const publicPages = [
      "/",
      "/planos",
      "/ajuda",
      "/termos",
      "/privacidade",
      "/observatorio/raio-x-saude-sp",
      "/licitacoes/saude",
      "/contratos/saude/sp",
      "/blog/licitacoes/saude",
      "/cnpj/12345678901234",
    ];

    it.each(publicPages)("%s is allowed", (route) => {
      expect(isAllowed(rules, route)).toBe(true);
    });
  });

  it("robots.txt contains explicit Allow: /alertas-publicos directive", () => {
    const content = fs.readFileSync(
      path.join(__dirname, "../../public/robots.txt"),
      "utf8"
    );
    expect(content).toMatch(/Allow:\s*\/alertas-publicos/);
  });

  it("robots.txt still contains Disallow: /alertas to block private panel", () => {
    const content = fs.readFileSync(
      path.join(__dirname, "../../public/robots.txt"),
      "utf8"
    );
    expect(content).toMatch(/Disallow:\s*\/alertas/);
  });
});
