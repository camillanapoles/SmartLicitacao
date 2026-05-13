/**
 * ProductWalkthrough — E2E Test (#1167)
 *
 * Verifica que o modal ProductWalkthrough funciona corretamente:
 * - Abertura via CTA no estado vazio do /buscar
 * - Navegacao entre passos (Próximo, Voltar)
 * - Fechamento via ESC, overlay click, Pular, Concluir
 * - localStorage "Não mostrar novamente"
 *
 * Pré-requisito: servidor de desenvolvimento rodando em localhost:3000
 */

import { test, expect } from "@playwright/test";

test.describe("ProductWalkthrough — Navegação e Interação", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/buscar");
    await page.evaluate(() => {
      localStorage.removeItem("smartlic_walkthrough_completed");
    });
  });

  test("CTA 'Veja como funciona' visível no estado vazio do /buscar", async ({
    page,
  }) => {
    const cta = page.getByText("Veja como funciona");
    await expect(cta).toBeVisible({ timeout: 5000 });
  });

  test("Modal abre ao clicar no CTA 'Veja como funciona'", async ({ page }) => {
    const cta = page.getByText("Veja como funciona");
    await cta.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 3000 });
    await expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  test("Modal mostra 'Passo 1 de 5' ao abrir", async ({ page }) => {
    await page.getByText("Veja como funciona").click();
    await expect(page.getByText("Passo 1 de 5")).toBeVisible({ timeout: 3000 });
  });

  test("Botão Voltar escondido no passo 1", async ({ page }) => {
    await page.getByText("Veja como funciona").click();
    await page.waitForTimeout(500);
    const backButton = page.getByTestId("walkthrough-back");
    await expect(backButton).not.toBeVisible();
  });

  test("Próximo avança para passo 2", async ({ page }) => {
    await page.getByText("Veja como funciona").click();
    await page.getByTestId("walkthrough-next").click();
    await page.waitForTimeout(300);
    await expect(page.getByText("Passo 2 de 5")).toBeVisible({ timeout: 3000 });
  });

  test("Voltar retorna ao passo 1 a partir do passo 2", async ({ page }) => {
    await page.getByText("Veja como funciona").click();
    await page.getByTestId("walkthrough-next").click();
    await page.waitForTimeout(300);
    await page.getByTestId("walkthrough-back").click();
    await page.waitForTimeout(300);
    await expect(page.getByText("Passo 1 de 5")).toBeVisible({ timeout: 3000 });
  });

  test("Botão Pular fecha o modal", async ({ page }) => {
    await page.getByText("Veja como funciona").click();
    await page.getByTestId("walkthrough-skip").click();
    await page.waitForTimeout(500);
    await expect(page.getByRole("dialog")).not.toBeVisible();
  });

  test("ESC fecha o modal", async ({ page }) => {
    await page.getByText("Veja como funciona").click();
    await page.waitForTimeout(500);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    await expect(page.getByRole("dialog")).not.toBeVisible();
  });

  test("Clique fora do modal fecha", async ({ page }) => {
    await page.getByText("Veja como funciona").click();
    await page.waitForTimeout(500);
    await page.locator('[data-testid="walkthrough-overlay"]').click({
      position: { x: 10, y: 10 },
    });
    await page.waitForTimeout(500);
    await expect(page.getByRole("dialog")).not.toBeVisible();
  });

  test("Checkbox 'Não mostrar novamente' persiste em localStorage", async ({
    page,
  }) => {
    await page.getByText("Veja como funciona").click();
    await page.waitForTimeout(300);
    await page.getByTestId("walkthrough-dont-show").check();
    await page.getByTestId("walkthrough-finish").click();
    // Avança até o último passo
    for (let i = 0; i < 4; i++) {
      const next = page.getByTestId("walkthrough-next");
      if (await next.isVisible().catch(() => false)) {
        await next.click();
        await page.waitForTimeout(200);
      }
    }
    // Clica Concluir
    const finish = page.getByTestId("walkthrough-finish");
    if (await finish.isVisible().catch(() => false)) {
      await finish.click();
    }
    await page.waitForTimeout(500);
    const completed = await page.evaluate(() =>
      localStorage.getItem("smartlic_walkthrough_completed")
    );
    expect(completed).toBe("true");
  });

  test("Modal não abre se localStorage tem 'smartlic_walkthrough_completed'", async ({
    page,
  }) => {
    await page.evaluate(() =>
      localStorage.setItem("smartlic_walkthrough_completed", "true")
    );
    await page.reload();
    await page.waitForTimeout(500);
    // O modal não deve aparecer espontaneamente
    const dialog = page.getByRole("dialog");
    await expect(dialog).not.toBeVisible();
  });
});
