/**
 * Tests for CnpjPerfilClient — SEM_HISTORICO fallback section.
 *
 * Verifies that the "Editais Abertos no seu Setor" section renders correctly
 * for companies with zero contracts, and stays hidden for ATIVO/INICIANTE.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock next/link
jest.mock('next/link', () => {
  return function MockLink({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) {
    return <a href={href} {...props}>{children}</a>;
  };
});

jest.mock('@/components/FollowButton', () => {
  return function MockFollowButton() {
    return <button data-testid="follow-button">Seguir</button>;
  };
});

import CnpjPerfilClient from '@/app/cnpj/[cnpj]/CnpjPerfilClient';

const BASE_EMPRESA = {
  razao_social: 'Empresa Teste LTDA',
  cnpj: '09225035000101',
  cnae_principal: '4781-4/00',
  porte: 'ME',
  uf: 'SP',
  situacao: 'ATIVA',
};

const SAMPLE_EDITAL = {
  orgao: 'PREFEITURA DE CAMPINAS',
  descricao: 'Aquisição de uniformes escolares para rede municipal',
  valor_estimado: 85000.0,
  data_encerramento: '2026-05-15',
  uf: 'SP',
  modalidade: 'Pregão Eletrônico',
};

function buildPerfil(overrides: Record<string, unknown> = {}) {
  return {
    empresa: BASE_EMPRESA,
    contratos: [],
    score: 'SEM_HISTORICO',
    setor_detectado: 'vestuario',
    setor_nome: 'Vestuário e Têxtil',
    editais_abertos_setor: 12,
    editais_amostra: [SAMPLE_EDITAL],
    total_contratos_24m: 0,
    valor_total_24m: 0,
    ufs_atuacao: [],
    aviso_legal: 'Dados de fontes públicas.',
    ...overrides,
  };
}

describe('CnpjPerfilClient — SEM_HISTORICO fallback section', () => {
  it('renders "Editais Abertos no seu Setor" when score=SEM_HISTORICO and editais_amostra is populated', () => {
    render(<CnpjPerfilClient perfil={buildPerfil()} />);
    expect(screen.getByText('Editais Abertos no seu Setor')).toBeInTheDocument();
  });

  it('renders the correct number of table rows', () => {
    const amostra = [SAMPLE_EDITAL, { ...SAMPLE_EDITAL, orgao: 'ESTADO DO RJ' }];
    render(<CnpjPerfilClient perfil={buildPerfil({ editais_amostra: amostra })} />);
    expect(screen.getAllByText(/PREFEITURA DE CAMPINAS|ESTADO DO RJ/).length).toBeGreaterThanOrEqual(1);
  });

  it('renders bid description in the table', () => {
    render(<CnpjPerfilClient perfil={buildPerfil()} />);
    expect(screen.getByText('Aquisição de uniformes escolares para rede municipal')).toBeInTheDocument();
  });

  it('does NOT render the section when editais_amostra is empty', () => {
    render(<CnpjPerfilClient perfil={buildPerfil({ editais_amostra: [] })} />);
    expect(screen.queryByText('Editais Abertos no seu Setor')).not.toBeInTheDocument();
  });

  it('does NOT render the section when contratos.length > 0 (ATIVO)', () => {
    const perfil = buildPerfil({
      score: 'ATIVO',
      contratos: [
        {
          orgao: 'Prefeitura X',
          valor: 100000,
          data_inicio: '2025-01-01',
          descricao: 'Obra qualquer',
          esfera: 'Municipal',
          uf: 'SP',
        },
      ],
      total_contratos_24m: 1,
      valor_total_24m: 100000,
      editais_amostra: [SAMPLE_EDITAL],
    });
    render(<CnpjPerfilClient perfil={perfil} />);
    expect(screen.queryByText('Editais Abertos no seu Setor')).not.toBeInTheDocument();
  });

  it('renders "—" for null valor_estimado', () => {
    const amostra = [{ ...SAMPLE_EDITAL, valor_estimado: null }];
    render(<CnpjPerfilClient perfil={buildPerfil({ editais_amostra: amostra })} />);
    // Should have at least one "—" for the null value
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(1);
  });

  it('renders "—" for null data_encerramento', () => {
    const amostra = [{ ...SAMPLE_EDITAL, data_encerramento: null }];
    render(<CnpjPerfilClient perfil={buildPerfil({ editais_amostra: amostra })} />);
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(1);
  });

  it('does NOT render the section for INICIANTE with contracts', () => {
    const perfil = buildPerfil({
      score: 'INICIANTE',
      contratos: [
        {
          orgao: 'Orgão Y',
          valor: 50000,
          data_inicio: '2025-06-01',
          descricao: 'Serviço qualquer',
          esfera: 'Estadual',
          uf: 'SP',
        },
      ],
      total_contratos_24m: 1,
      editais_amostra: [SAMPLE_EDITAL],
    });
    render(<CnpjPerfilClient perfil={perfil} />);
    expect(screen.queryByText('Editais Abertos no seu Setor')).not.toBeInTheDocument();
  });

  it('shows fonte attribution text', () => {
    render(<CnpjPerfilClient perfil={buildPerfil()} />);
    expect(
      screen.getByText(/Portal Nacional de Contratações Públicas/)
    ).toBeInTheDocument();
  });

  it('shows setor_nome in the intro paragraph', () => {
    render(<CnpjPerfilClient perfil={buildPerfil()} />);
    expect(screen.getAllByText(/Vestuário e Têxtil/).length).toBeGreaterThanOrEqual(1);
  });
});
