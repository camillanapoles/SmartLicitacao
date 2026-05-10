/**
 * Tests for PSEOTemplate (#1004 COPY-PSEO-005).
 *
 * Cobre:
 *  - Interpolação de variáveis (H1, totalOpenSemana, valorMedio).
 *  - Beachhead positioning: município sobrescreve UF.
 *  - FAQ helper (5 perguntas, ancoragem em dados reais).
 *  - JSON-LD FAQPage estrutura schema.org.
 *  - Voice gate: lista de palavras banidas não aparece.
 *  - Slot dataBlock (#1007 wiring).
 */
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import PSEOTemplate, {
  PSEOContext,
  buildPSEOH1,
  buildPSEOFaqs,
  buildFaqJsonLd,
} from "../PSEOTemplate";

const baseCtx: PSEOContext = {
  setor: "Pavimentação asfáltica",
  setorSlug: "pavimentacao-asfaltica",
  ufNome: "Santa Catarina",
  ufSigla: "SC",
  totalOpen: 47,
  totalOpenSemana: 12,
  valorMedio: "R$ 320.000",
  valorMin: "R$ 80.000",
  valorMax: "R$ 1.200.000",
  modalidadeTop: "Pregão Eletrônico",
  modalidadePercents: { pregao: 78, concorrencia: 15, dispensa: 7 },
  planoMensal: "R$ 397",
  dataHoje: "10/05/2026",
};

const BANNED_WORDS = [
  "outrossim",
  "no que tange",
  "robusta",
  "ecossistema",
  "stakeholders",
];

describe("buildPSEOH1", () => {
  it("interpola setor + total + UF nome", () => {
    expect(buildPSEOH1(baseCtx)).toBe(
      "47 editais abertos de Pavimentação asfáltica em Santa Catarina"
    );
  });

  it("usa município (beachhead) quando presente, com sigla UF entre parênteses", () => {
    const ctx: PSEOContext = {
      ...baseCtx,
      municipio: "Joinville",
      totalOpenMunicipio: 9,
    };
    expect(buildPSEOH1(ctx)).toBe(
      "9 editais abertos de Pavimentação asfáltica em Joinville (SC)"
    );
  });

  it("usa total geral quando município existe mas totalOpenMunicipio ausente", () => {
    const ctx: PSEOContext = { ...baseCtx, municipio: "Joinville" };
    expect(buildPSEOH1(ctx)).toContain("47 editais abertos");
    expect(buildPSEOH1(ctx)).toContain("Joinville (SC)");
  });

  it("usa Brasil quando UF e município ausentes (página somente setor)", () => {
    const ctx: PSEOContext = {
      ...baseCtx,
      ufNome: undefined,
      ufSigla: undefined,
    };
    expect(buildPSEOH1(ctx)).toContain("em Brasil");
  });
});

describe("buildPSEOFaqs", () => {
  it("retorna exatamente 5 perguntas com perguntas obrigatórias", () => {
    const faqs = buildPSEOFaqs(baseCtx);
    expect(faqs).toHaveLength(5);
    const questions = faqs.map((f) => f.question);
    expect(questions[0]).toContain("modalidades");
    expect(questions[1]).toContain("ticket médio");
    expect(questions[2]).toContain("novo edital");
    expect(questions[3]).toContain("assessor");
    expect(questions[4]).toContain("Quanto custa");
  });

  it("ancora resposta de modalidades em percentuais reais", () => {
    const faqs = buildPSEOFaqs(baseCtx);
    expect(faqs[0].answer).toContain("78%");
    expect(faqs[0].answer).toContain("15%");
    expect(faqs[0].answer).toContain("7%");
  });

  it("usa fallback quando modalidadePercents ausente", () => {
    const ctx = { ...baseCtx, modalidadePercents: undefined };
    const faqs = buildPSEOFaqs(ctx);
    expect(faqs[0].answer).toContain("Pregão Eletrônico");
    expect(faqs[0].answer).not.toContain("undefined");
  });

  it("ancora ticket médio em valorMedio + faixa min/max", () => {
    const faqs = buildPSEOFaqs(baseCtx);
    expect(faqs[1].answer).toContain("R$ 320.000");
    expect(faqs[1].answer).toContain("R$ 80.000");
    expect(faqs[1].answer).toContain("R$ 1.200.000");
  });

  it("usa planoMensal customizado na FAQ de preço", () => {
    const ctx = { ...baseCtx, planoMensal: "R$ 297" };
    const faqs = buildPSEOFaqs(ctx);
    expect(faqs[4].answer).toContain("R$ 297");
    expect(faqs[4].answer).toContain("R$ 997");
  });
});

describe("buildFaqJsonLd", () => {
  it("emite FAQPage schema.org válido com 5 questions", () => {
    const ld = buildFaqJsonLd(baseCtx) as {
      "@context": string;
      "@type": string;
      mainEntity: Array<{ "@type": string; name: string; acceptedAnswer: { "@type": string; text: string } }>;
    };
    expect(ld["@context"]).toBe("https://schema.org");
    expect(ld["@type"]).toBe("FAQPage");
    expect(ld.mainEntity).toHaveLength(5);
    ld.mainEntity.forEach((q) => {
      expect(q["@type"]).toBe("Question");
      expect(q.name).toBeTruthy();
      expect(q.acceptedAnswer["@type"]).toBe("Answer");
      expect(q.acceptedAnswer.text.length).toBeGreaterThan(50);
    });
  });
});

describe("PSEOTemplate render", () => {
  it("renderiza H1 com variáveis interpoladas", () => {
    render(<PSEOTemplate ctx={baseCtx} />);
    expect(
      screen.getByRole("heading", { level: 1 })
    ).toHaveTextContent("47 editais abertos de Pavimentação asfáltica em Santa Catarina");
  });

  it("renderiza CTA inline com totalOpenSemana e setor", () => {
    render(<PSEOTemplate ctx={baseCtx} />);
    expect(
      screen.getByText(/12 editais de Pavimentação asfáltica em Santa Catarina/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Receber alertas grátis 14 dias/)).toBeInTheDocument();
    expect(screen.getByText(/Só quero ver os dados/)).toBeInTheDocument();
  });

  it("renderiza sticky CTA mobile com total + setor", () => {
    render(<PSEOTemplate ctx={baseCtx} />);
    const sticky = screen.getByTestId("pseo-sticky-cta");
    expect(sticky).toHaveTextContent("47 editais abertos");
    expect(sticky).toHaveTextContent("Pavimentação asfáltica");
  });

  it("renderiza banner Founders rodapé com R$ 997 e 30/06", () => {
    render(<PSEOTemplate ctx={baseCtx} />);
    // R$ 997 aparece também na FAQ de preço (cross-sell duplo); validamos
    // a frase exata do banner rodapé.
    expect(
      screen.getByText(/Vai usar SmartLic todo mês\?.+R\$ 997.+50 vagas, encerra 30\/06/)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Saber mais/ })
    ).toHaveAttribute("href", expect.stringContaining("/fundadores"));
  });

  it("renderiza dataHoje no sub-hero", () => {
    render(<PSEOTemplate ctx={baseCtx} />);
    expect(screen.getByText(/Atualizado em 10\/05\/2026/)).toBeInTheDocument();
  });

  it("renderiza slot dataBlock quando provido (wiring #1007)", () => {
    render(
      <PSEOTemplate
        ctx={baseCtx}
        dataBlock={<div data-testid="custom-data">DATA</div>}
      />
    );
    expect(screen.getByTestId("pseo-data-block-slot")).toBeInTheDocument();
    expect(screen.getByTestId("custom-data")).toBeInTheDocument();
  });

  it("omite slot dataBlock quando ausente", () => {
    render(<PSEOTemplate ctx={baseCtx} />);
    expect(screen.queryByTestId("pseo-data-block-slot")).not.toBeInTheDocument();
  });

  it("usa município no H1 quando presente (beachhead)", () => {
    render(
      <PSEOTemplate
        ctx={{ ...baseCtx, municipio: "Joinville", totalOpenMunicipio: 9 }}
      />
    );
    expect(
      screen.getByRole("heading", { level: 1 })
    ).toHaveTextContent("9 editais abertos de Pavimentação asfáltica em Joinville (SC)");
  });

  it("não emite nenhuma palavra banida (voice gate)", () => {
    const { container } = render(<PSEOTemplate ctx={baseCtx} />);
    const text = (container.textContent ?? "").toLowerCase();
    BANNED_WORDS.forEach((word) => {
      expect(text).not.toContain(word.toLowerCase());
    });
  });

  it("emite JSON-LD FAQPage no DOM", () => {
    const { container } = render(<PSEOTemplate ctx={baseCtx} />);
    const ldScript = container.querySelector('script[type="application/ld+json"]');
    expect(ldScript).not.toBeNull();
    const parsed = JSON.parse(ldScript!.innerHTML);
    expect(parsed["@type"]).toBe("FAQPage");
    expect(parsed.mainEntity).toHaveLength(5);
  });
});
