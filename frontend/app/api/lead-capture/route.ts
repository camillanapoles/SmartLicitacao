import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      email,
      source,
      setor,
      uf,
      // REPO-014: extended fields for DiagnosticForm
      nome,
      empresa,
      cnpj,
      modalidade_interesse,
      mensagem,
      telefone,
      // UTM params forwarded from the client
      utm_source,
      utm_medium,
      utm_campaign,
      utm_content,
      utm_term,
    } = body as Record<string, string | undefined>;

    const hasPhone = typeof telefone === 'string' && telefone.trim().length >= 10;

    if ((!email || !email.includes('@')) && !hasPhone) {
      return NextResponse.json(
        { error: 'Email ou telefone inválido' },
        { status: 400 },
      );
    }

    // Store in Supabase via backend proxy
    const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;
    const res = await fetch(`${backendUrl}/v1/lead-capture`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        source,
        setor: setor || null,
        uf: uf || null,
        nome: nome || null,
        empresa: empresa || null,
        cnpj: cnpj || null,
        modalidade_interesse: modalidade_interesse || null,
        mensagem: mensagem || null,
        telefone: telefone || null,
        utm_source: utm_source || null,
        utm_medium: utm_medium || null,
        utm_campaign: utm_campaign || null,
        utm_content: utm_content || null,
        utm_term: utm_term || null,
        captured_at: new Date().toISOString(),
      }),
    });

    if (!res.ok) {
      const requestId = res.headers.get('x-request-id');
      console.warn('Lead capture backend returned non-OK response', {
        status: res.status,
        requestId,
      });
      return NextResponse.json(
        { success: false, error: `Erro ao processar (${res.status})` },
        { status: 502 },
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Lead capture error:', error);
    return NextResponse.json(
      { success: false, error: 'Serviço indisponível. Tente novamente.' },
      { status: 502 },
    );
  }
}
