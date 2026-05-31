-- CONV-005b-1: Schema digital_products para microtransacoes
--
-- Produtos digitais avulsos (one-time payment) disponiveis para compra
-- sem assinatura. Fundacao do checkout modular (CONV-005b).

CREATE TABLE digital_products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sku TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  price_brl INTEGER NOT NULL,                -- preco em centavos (BRL)
  stripe_product_id TEXT,                     -- ID do Product no Stripe
  stripe_price_id TEXT,                       -- ID do Price no Stripe
  preview_config JSONB DEFAULT '{}',          -- configuracao de preview (qtd blur, etc.)
  delivery_config JSONB DEFAULT '{}',         -- configuracao de entrega (tipo, template)
  upsell_product_id UUID REFERENCES digital_products(id),
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indice para busca por SKU ativo
CREATE INDEX idx_digital_products_active_sku ON digital_products(sku) WHERE active = true;

-- Seed dos 5 produtos iniciais
INSERT INTO digital_products (sku, name, description, price_brl, preview_config, delivery_config) VALUES
  ('relatorio-oportunidade', 'Relatorio de Oportunidade Setorial', 'Analise completa de oportunidades em um setor especifico com projecao de demanda e ranking de orgaos compradores', 4700, '{"max_free_items": 3, "blurred_items": 3}', '{"type": "pdf", "template": "relatorio-oportunidade"}'),
  ('fornecedores-vencedores', 'Fornecedores Vencedores', 'Lista detalhada de fornecedores que mais ganham contratos em um setor/UF, com ticket medio e taxa de vitoria estimada', 6700, '{"max_free_items": 3, "blurred_items": 5}', '{"type": "pdf", "template": "fornecedores-vencedores"}'),
  ('orgaos-compradores', 'Orgaos Compradores', 'Mapeamento dos principais orgaos compradores por setor com volume de contratos e sazonalidade', 4700, '{"max_free_items": 3, "blurred_items": 3}', '{"type": "pdf", "template": "orgaos-compradores"}'),
  ('subcontratacao-map', 'Mapa de Subcontratacao', 'Fornecedores com capacidade sobrecarregada que provavelmente subcontratarao, com score de oportunidade', 9700, '{"max_free_items": 2, "blurred_items": 5}', '{"type": "pdf", "template": "subcontratacao-map"}'),
  ('alerta-semanal', 'Alerta Semanal de Oportunidades', 'Monitoramento semanal personalizado de novos editais e contratos no seu setor e UFs de interesse', 2990, '{"max_free_items": 2, "blurred_items": 3}', '{"type": "email", "template": "alerta-semanal"}')
ON CONFLICT (sku) DO NOTHING;

-- RLS: leitura publica para checkout, admin gerencia
ALTER TABLE digital_products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Produtos ativos visiveis para todos" ON digital_products
  FOR SELECT USING (active = true);

CREATE POLICY "Admin gerencia produtos" ON digital_products
  FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND is_admin = true));

-- Grants
GRANT SELECT ON digital_products TO anon, authenticated;
GRANT ALL ON digital_products TO service_role;
