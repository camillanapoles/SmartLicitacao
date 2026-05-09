/**
 * E2E Test: Intel Reports Checkout Flow — Issue #827
 *
 * Covers the full purchase journey for Intel Reports (Raio-X do Concorrente):
 *   TC-01 — CTA button is visible on /cnpj/[cnpj] (page is public SSG, no auth required)
 *   TC-02 — Unauthenticated click → checkout 401 → router.push to /signup?intent=intel_report
 *   TC-03 — Loading state shown while checkout is in-flight ("Aguarde...")
 *   TC-04 — Cancel page /intel-reports/cancelado renders with return CTA to /
 *   TC-05 — Success page shows processing/polling state when report is pending
 *   TC-06 — Success page shows "Baixar Relatório (PDF)" button when status is "ready"
 *
 * Network interception strategy (page.route — never calls real APIs):
 *   - /api/intel-reports/checkout → mocked (POST returns fake Stripe URL or 401)
 *   - /api/intel-reports          → mocked (GET returns list with purchase status)
 *   - /v1/empresa/{cnpj}/perfil-b2g → mocked (CNPJ profile for ISR page)
 *
 * Implementation notes (deviations from task spec — grounded in source code):
 *   - TC-01: Page is ISR/SSG and public; IntelReportCTA renders regardless of auth state.
 *     No login step needed.
 *   - TC-02: Redirect fires on checkout 401, not on page visit without auth. URL contains
 *     `intent=intel_report` (plus `redirect=` param). Assert with regex.
 *   - TC-03: Loading text is "Aguarde..." (IntelReportCTA.tsx:72), not "Processando".
 *   - TC-04: Cancel page returns to "/" ("Voltar ao início"), not "/buscar".
 *   - TC-05/TC-06: Success page polls GET /api/intel-reports (list) and takes items[0].
 *     Mock returns array, not single object.
 */

import { test, expect } from '@playwright/test';
import { clearTestData } from './helpers/test-utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** CNPJ used in all tests. Public CNPJ — known to have profile data in DataLake. */
const TEST_CNPJ = '33683111000107';

/** Fake Stripe checkout URL that we intercept to avoid leaving the app. */
const FAKE_STRIPE_URL = 'https://checkout.stripe.com/pay/cs_test_intel_mock';

// ---------------------------------------------------------------------------
// Shared mock helpers
// ---------------------------------------------------------------------------

/**
 * Mock the CNPJ perfil endpoint so /cnpj/[cnpj] renders without hitting the backend.
 * The page is ISR; in dev mode it calls the backend. Mock prevents flakiness.
 */
async function mockCnpjPerfilAPI(page: Parameters<typeof clearTestData>[0]) {
  await page.route('**/v1/empresa/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        empresa: {
          razao_social: 'EMPRESA TESTE LTDA',
          cnpj: TEST_CNPJ,
          cnae_principal: '4711-3/02',
          porte: 'MEDIO',
          uf: 'SP',
          situacao: 'ATIVA',
        },
        contratos: [],
        score: 'A',
        setor_detectado: 'vestuario',
        setor_nome: 'Vestuário e Uniformes',
        editais_abertos_setor: 5,
        editais_amostra: [],
        total_contratos_24m: 3,
        valor_total_24m: 150000,
        ufs_atuacao: ['SP'],
        aviso_legal: 'Dados meramente ilustrativos.',
      }),
    });
  });
}

/**
 * Mock POST /api/intel-reports/checkout.
 * Pass status=401 to simulate unauthenticated response;
 * otherwise returns a fake checkout_url.
 */
async function mockCheckoutAPI(
  page: Parameters<typeof clearTestData>[0],
  options: { httpStatus?: number; checkoutUrl?: string; delayMs?: number } = {}
) {
  const { httpStatus = 200, checkoutUrl = FAKE_STRIPE_URL, delayMs = 0 } = options;

  await page.route('**/api/intel-reports/checkout', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }

    if (delayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }

    if (httpStatus === 401) {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      });
      return;
    }

    await route.fulfill({
      status: httpStatus,
      contentType: 'application/json',
      body: JSON.stringify({ checkout_url: checkoutUrl, session_id: 'cs_test_intel_mock' }),
    });
  });
}

/**
 * Mock GET /api/intel-reports (list endpoint polled by success page).
 * Returns an array with a single purchase entry.
 */
async function mockIntelReportListAPI(
  page: Parameters<typeof clearTestData>[0],
  purchase: {
    id?: string;
    status: 'pending' | 'generating' | 'ready' | 'failed';
    pdf_url?: string;
    expires_at?: string;
  }
) {
  const entry = {
    id: purchase.id ?? 'purchase-test-uuid-001',
    status: purchase.status,
    pdf_url: purchase.pdf_url,
    expires_at: purchase.expires_at ?? new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  };

  await page.route('**/api/intel-reports', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([entry]),
    });
  });
}

// ---------------------------------------------------------------------------
// TC-01 — CTA visible on /cnpj/[cnpj] (public SSG page, no auth required)
// ---------------------------------------------------------------------------

test.describe('TC-01 — CTA visible on /cnpj/[cnpj]', () => {
  test.beforeEach(async ({ page }) => {
    await clearTestData(page);
    await mockCnpjPerfilAPI(page);
  });

  test('renders "Comprar Raio-X" button visible', async ({ page }) => {
    await page.goto(`/cnpj/${TEST_CNPJ}`);

    // The button uses text content set by IntelReportCTA (no data-testid).
    // Exact text: "Comprar Raio-X — R$197" when not loading.
    const ctaButton = page.getByRole('button', { name: /Comprar Raio-X/i }).first();
    await expect(ctaButton).toBeVisible({ timeout: 15000 });
    await expect(ctaButton).toBeEnabled();
  });

  test('section heading "Inteligência Competitiva" is visible', async ({ page }) => {
    await page.goto(`/cnpj/${TEST_CNPJ}`);

    const heading = page.getByText('Inteligência Competitiva').first();
    await expect(heading).toBeVisible({ timeout: 15000 });
  });

  test('screenshot — CTA section visible', async ({ page }) => {
    await page.goto(`/cnpj/${TEST_CNPJ}`);

    const ctaButton = page.getByRole('button', { name: /Comprar Raio-X/i }).first();
    await expect(ctaButton).toBeVisible({ timeout: 15000 });

    await page.screenshot({ path: 'screenshots/tc-01-intel-cta-visible.png', fullPage: false });
  });
});

// ---------------------------------------------------------------------------
// TC-02 — Unauthenticated click → checkout 401 → redirect to /signup?intent=intel_report
// ---------------------------------------------------------------------------

test.describe('TC-02 — 401 on checkout → redirect to signup with intent=intel_report', () => {
  test.beforeEach(async ({ page }) => {
    await clearTestData(page);
    await mockCnpjPerfilAPI(page);
  });

  test('routes to /signup with intent=intel_report when checkout returns 401', async ({ page }) => {
    // Simulate unauthenticated: checkout API returns 401
    await mockCheckoutAPI(page, { httpStatus: 401 });

    await page.goto(`/cnpj/${TEST_CNPJ}`);

    const ctaButton = page.getByRole('button', { name: /Comprar Raio-X/i }).first();
    await expect(ctaButton).toBeVisible({ timeout: 15000 });

    // Navigate event after redirect — router.push fires on 401
    await Promise.all([
      page.waitForURL(/intent=intel_report/, { timeout: 10000 }),
      ctaButton.click(),
    ]);

    // URL must contain intent=intel_report (and optionally redirect param)
    expect(page.url()).toMatch(/intent=intel_report/);

    // Also verify we landed somewhere in the signup flow
    expect(page.url()).toMatch(/\/signup/);
  });

  test('redirect URL also includes redirect param pointing to cnpj page', async ({ page }) => {
    await mockCheckoutAPI(page, { httpStatus: 401 });

    await page.goto(`/cnpj/${TEST_CNPJ}`);

    const ctaButton = page.getByRole('button', { name: /Comprar Raio-X/i }).first();
    await expect(ctaButton).toBeVisible({ timeout: 15000 });

    await Promise.all([
      page.waitForURL(/signup/, { timeout: 10000 }),
      ctaButton.click(),
    ]);

    // IntelReportCTA uses: /signup?redirect=/cnpj/${cnpj}&intent=intel_report
    const url = page.url();
    expect(url).toMatch(/redirect=/);
    expect(url).toMatch(new RegExp(TEST_CNPJ));
  });
});

// ---------------------------------------------------------------------------
// TC-03 — Loading state shown while checkout is in-flight
// ---------------------------------------------------------------------------

test.describe('TC-03 — Loading state ("Aguarde...") during checkout', () => {
  test.beforeEach(async ({ page }) => {
    await clearTestData(page);
    await mockCnpjPerfilAPI(page);
  });

  test('button shows "Aguarde..." text while checkout request is in-flight', async ({ page }) => {
    // Delay checkout response so we can observe loading state
    await mockCheckoutAPI(page, { checkoutUrl: FAKE_STRIPE_URL, delayMs: 500 });

    // Block Stripe redirect so the test doesn't leave the app
    await page.route('https://checkout.stripe.com/**', async (route) => {
      await route.abort('aborted');
    });

    // Also block window.location.href navigation to Stripe
    await page.addInitScript(() => {
      // Override window.location assignment to prevent navigation to external Stripe URL
      Object.defineProperty(window, '_interceptedHref', { value: null, writable: true });
    });

    await page.goto(`/cnpj/${TEST_CNPJ}`);

    const ctaButton = page.getByRole('button', { name: /Comprar Raio-X/i }).first();
    await expect(ctaButton).toBeVisible({ timeout: 15000 });
    await expect(ctaButton).toBeEnabled();

    // Click without awaiting full navigation — we want to catch loading state
    await ctaButton.click();

    // Button should immediately show loading text and be disabled
    await expect(ctaButton).toHaveText(/Aguarde\.\.\./i, { timeout: 3000 });
    await expect(ctaButton).toBeDisabled();
  });

  test('button is disabled (opacity-60) in loading state', async ({ page }) => {
    await mockCheckoutAPI(page, { checkoutUrl: FAKE_STRIPE_URL, delayMs: 400 });
    await page.route('https://checkout.stripe.com/**', async (route) => {
      await route.abort('aborted');
    });

    await page.goto(`/cnpj/${TEST_CNPJ}`);

    const ctaButton = page.getByRole('button', { name: /Comprar Raio-X/i }).first();
    await expect(ctaButton).toBeVisible({ timeout: 15000 });

    await ctaButton.click();

    // Verify disabled attribute is set on loading
    await expect(ctaButton).toBeDisabled({ timeout: 3000 });
  });
});

// ---------------------------------------------------------------------------
// TC-04 — Cancel page /intel-reports/cancelado renders correctly
// ---------------------------------------------------------------------------

test.describe('TC-04 — /intel-reports/cancelado page', () => {
  test.beforeEach(async ({ page }) => {
    await clearTestData(page);
  });

  test('renders "Compra cancelada" heading', async ({ page }) => {
    await page.goto('/intel-reports/cancelado');

    const heading = page.getByRole('heading', { name: /Compra cancelada/i }).first();
    await expect(heading).toBeVisible({ timeout: 10000 });
  });

  test('shows message that no charge was made', async ({ page }) => {
    await page.goto('/intel-reports/cancelado');

    const message = page.getByText(/Nenhuma cobrança foi realizada/i).first();
    await expect(message).toBeVisible({ timeout: 10000 });
  });

  test('has return CTA link pointing to "/" (home, not /buscar)', async ({ page }) => {
    await page.goto('/intel-reports/cancelado');

    // Cancel page returns to home: <Link href="/">Voltar ao início</Link>
    const returnLink = page.getByRole('link', { name: /Voltar ao início/i }).first();
    await expect(returnLink).toBeVisible({ timeout: 10000 });

    const href = await returnLink.getAttribute('href');
    expect(href).toBe('/');
  });

  test('screenshot — cancel page renders', async ({ page }) => {
    await page.goto('/intel-reports/cancelado');

    const heading = page.getByRole('heading', { name: /Compra cancelada/i }).first();
    await expect(heading).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: 'screenshots/tc-04-intel-cancelado.png', fullPage: false });
  });
});

// ---------------------------------------------------------------------------
// TC-05 — Success page shows processing/polling state (status: pending)
// ---------------------------------------------------------------------------

test.describe('TC-05 — /intel-reports/[sessionId] shows polling state (pending)', () => {
  test.beforeEach(async ({ page }) => {
    await clearTestData(page);
  });

  test('shows processing heading and spinner while status is pending', async ({ page }) => {
    // Mock list API returning pending status — page polls this
    await mockIntelReportListAPI(page, { status: 'pending' });

    await page.goto('/intel-reports/cs_test_processing_session');

    // Heading in pending state: "Gerando seu relatório..."
    const heading = page.getByRole('heading').first();
    await expect(heading).toBeVisible({ timeout: 15000 });
    await expect(heading).toContainText(/gerando|processando/i);
  });

  test('shows animate-spin spinner in processing state', async ({ page }) => {
    await mockIntelReportListAPI(page, { status: 'pending' });

    // Delay the response slightly to ensure we see the initial loading state
    await page.route('**/api/intel-reports', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'purchase-001', status: 'pending' }]),
      });
    });

    await page.goto('/intel-reports/cs_test_processing_session');

    // Spinner: <div class="h-10 w-10 animate-spin rounded-full border-b-2 border-blue-600">
    const spinner = page.locator('.animate-spin').first();
    await expect(spinner).toBeVisible({ timeout: 10000 });
  });

  test('polls GET /api/intel-reports (the list endpoint) at least once', async ({ page }) => {
    let pollCount = 0;

    await page.route('**/api/intel-reports', async (route) => {
      if (route.request().method() === 'GET') {
        pollCount += 1;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'purchase-001', status: 'pending' }]),
      });
    });

    await page.goto('/intel-reports/cs_test_processing_session');

    // Wait for at least one poll cycle (1500ms initial delay + render)
    await page.waitForTimeout(2500);

    expect(pollCount).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// TC-06 — Success page shows "Baixar Relatório (PDF)" when status is ready
// ---------------------------------------------------------------------------

test.describe('TC-06 — /intel-reports/[sessionId] shows download button when ready', () => {
  const PURCHASE_ID = 'purchase-ready-uuid-001';

  test.beforeEach(async ({ page }) => {
    await clearTestData(page);
  });

  test('shows "Relatório pronto!" heading when status is ready', async ({ page }) => {
    await mockIntelReportListAPI(page, {
      id: PURCHASE_ID,
      status: 'ready',
      pdf_url: 'https://storage.example.com/report.pdf',
    });

    await page.goto('/intel-reports/cs_test_ready_session');

    const heading = page.getByRole('heading', { name: /Relatório pronto/i }).first();
    await expect(heading).toBeVisible({ timeout: 10000 });
  });

  test('shows "Baixar Relatório (PDF)" button when status is ready', async ({ page }) => {
    await mockIntelReportListAPI(page, {
      id: PURCHASE_ID,
      status: 'ready',
      pdf_url: 'https://storage.example.com/report.pdf',
    });

    await page.goto('/intel-reports/cs_test_ready_session');

    // Button text: "Baixar Relatório (PDF)" — calls window.open
    const downloadBtn = page.getByRole('button', { name: /Baixar Relatório/i }).first();
    await expect(downloadBtn).toBeVisible({ timeout: 10000 });
    await expect(downloadBtn).toBeEnabled();
  });

  test('download button calls /api/intel-reports/{id}/download via window.open', async ({ page }) => {
    await mockIntelReportListAPI(page, {
      id: PURCHASE_ID,
      status: 'ready',
      pdf_url: 'https://storage.example.com/report.pdf',
    });

    // Intercept the download route that window.open triggers (_blank popup)
    let downloadRouteHit = false;
    await page.route(`**/api/intel-reports/${PURCHASE_ID}/download`, async (route) => {
      downloadRouteHit = true;
      await route.fulfill({ status: 200, body: 'PDF content' });
    });

    await page.goto('/intel-reports/cs_test_ready_session');

    const downloadBtn = page.getByRole('button', { name: /Baixar Relatório/i }).first();
    await expect(downloadBtn).toBeVisible({ timeout: 10000 });

    // Intercept popup to prevent actual download window
    const popupPromise = page.waitForEvent('popup').catch(() => null);
    await downloadBtn.click();

    // Either a popup was opened or the route was hit (window.open behavior varies)
    const popup = await popupPromise;
    if (popup) {
      await popup.close();
      // Verify the URL contains the correct download path
      expect(popup.url()).toContain(PURCHASE_ID);
    } else {
      // Fallback: verify route was intercepted
      await page.waitForTimeout(500);
      expect(downloadRouteHit).toBe(true);
    }
  });

  test('shows upsell link to /planos after ready state', async ({ page }) => {
    await mockIntelReportListAPI(page, {
      id: PURCHASE_ID,
      status: 'ready',
    });

    await page.goto('/intel-reports/cs_test_ready_session');

    // Success page shows: <Link href="/planos" ...>Conhecer planos</Link>
    const plansLink = page.getByRole('link', { name: /Conhecer planos/i }).first();
    await expect(plansLink).toBeVisible({ timeout: 10000 });
  });

  test('screenshot — ready state with download button', async ({ page }) => {
    await mockIntelReportListAPI(page, {
      id: PURCHASE_ID,
      status: 'ready',
    });

    await page.goto('/intel-reports/cs_test_ready_session');

    const downloadBtn = page.getByRole('button', { name: /Baixar Relatório/i }).first();
    await expect(downloadBtn).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: 'screenshots/tc-06-intel-ready-download.png', fullPage: false });
  });
});
