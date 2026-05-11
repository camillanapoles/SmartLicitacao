/**
 * S7+S11: Author registry for Person schema, blog bylines, and author pages.
 * Used by: /blog/author/[slug], BlogArticleLayout, sitemap, RSS feeds.
 */

export interface Author {
  slug: string;
  name: string;
  role: string;
  bio: string;
  shortBio: string;
  image: string;
  credentials: string[];
  socialLinks: {
    linkedin?: string;
    github?: string;
  };
  sameAs: string[];
  knowsAbout: string[];
}

export const AUTHORS: Author[] = [
  {
    slug: 'tiago-sasaki',
    name: 'Tiago Sasaki',
    role: 'CEO & CTO',
    bio: 'Engenheiro e empreendedor com experiência em avaliações de ativos, inteligência artificial e contratações públicas. Fundador da CONFENGE Avaliações e Inteligência Artificial LTDA, empresa por trás do SmartLic — plataforma que transforma a análise de licitações públicas de intuitiva para objetiva usando IA e dados do PNCP. Desenvolvedor full-stack com foco em arquiteturas escaláveis para mercados B2G.',
    shortBio: 'CEO & CTO da CONFENGE, especialista em IA aplicada a licitações públicas.',
    image: 'https://smartlic.tech/authors/tiago-sasaki.webp',
    credentials: [
      'Engenheiro de Avaliações',
      'Especialista em IA aplicada a contratações públicas',
      'Fundador da CONFENGE Avaliações e IA LTDA',
      'Desenvolvedor Full-Stack (Python, TypeScript)',
    ],
    socialLinks: {
      linkedin: 'https://www.linkedin.com/in/tiagosasaki',
      github: 'https://github.com/tjsasakifln',
    },
    sameAs: [
      'https://www.linkedin.com/in/tiagosasaki',
      'https://github.com/tjsasakifln',
    ],
    knowsAbout: [
      'Licitações Públicas',
      'Lei 14.133/2021',
      'Inteligência Artificial',
      'Análise de Viabilidade',
      'Contratações Governamentais',
      'Pregão Eletrônico',
    ],
  },
];

export const DEFAULT_AUTHOR_SLUG = 'tiago-sasaki';

export function getAuthorBySlug(slug: string): Author | undefined {
  return AUTHORS.find((a) => a.slug === slug);
}

export function getAllAuthorSlugs(): string[] {
  return AUTHORS.map((a) => a.slug);
}
