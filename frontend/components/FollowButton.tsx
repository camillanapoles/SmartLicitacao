'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/app/components/AuthProvider';
import { fetchWithAuth } from '@/lib/fetchWithAuth';
import mixpanel from 'mixpanel-browser';
import { getCookieConsent } from '@/app/components/CookieConsentBanner';

interface FollowButtonProps {
  entityType: 'orgao' | 'fornecedor';
  entityId: string;
  entityName: string;
  entityCnpj: string;
}
interface AlertRecord { id: string; name: string; tracked_orgaos: string[]; tracked_fornecedores: string[]; [key: string]: unknown; }

const PLAN_LIMITS: Record<string, number> = { free_trial: 1, smartlic_pro: 5, consultoria: 20, master: 20 };
const DEF_LIMIT = 1;

function countTracked(a: AlertRecord[], f: 'tracked_orgaos'|'tracked_fornecedores'): number {
  const s = new Set<string>(); for (const al of a) { const l = al[f]; if (Array.isArray(l)) l.forEach(c => s.add(c)); } return s.size;
}
function canTrack(): boolean {
  if (typeof window === 'undefined') return false;
  if (!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN) return false;
  try { return getCookieConsent()?.analytics === true; } catch { return false; }
}
function safeTrack(n: string, p: Record<string, unknown>) {
  if (!canTrack()) return;
  try { mixpanel.track(n, { ...p, timestamp: new Date().toISOString(), environment: process.env.NODE_ENV || 'development' }); } catch {}
}

export default function FollowButton({ entityType, entityId, entityName, entityCnpj }: FollowButtonProps) {
  const router = useRouter(); const { user, loading: authL } = useAuth();
  const tf = entityType === 'orgao' ? 'tracked_orgaos' : 'tracked_fornecedores';
  const el = entityType === 'orgao' ? 'orgao' : 'fornecedor';
  const fl = entityType === 'orgao' ? 'Seguir orgao' : 'Seguir fornecedor';
  const [f, sf] = useState(false); const [ck, sck] = useState(true); const [al, sal] = useState(false); const [er, ser] = useState<string|null>(null); const [lr, slr] = useState(false); const [aid, said] = useState<string|null>(null);
  const mr = useRef(true);

  const check = useCallback(async () => {
    if (!user) { if (mr.current) sck(false); return; }
    try {
      const r = await fetchWithAuth('/api/alerts'); if (!r.ok) { if (mr.current) sck(false); return; }
      const d = await r.json(); const alr: AlertRecord[] = Array.isArray(d) ? d : (d.alerts ?? []);
      let fa = null; let it = false;
      for (const a of alr) { const l = a[tf]; if (Array.isArray(l) && l.includes(entityCnpj)) { it = true; fa = a.id; break; } }
      if (!it) { const cc = countTracked(alr, tf); const pt = (user.app_metadata?.plan_type as string) ?? 'free_trial'; if (cc >= (PLAN_LIMITS[pt] ?? DEF_LIMIT) && mr.current) slr(true); }
      if (mr.current) { sf(it); said(fa); sck(false); }
    } catch { if (mr.current) sck(false); }
  }, [user, entityCnpj, tf]);
  useEffect(() => { check(); }, [check]);

  const toggle = useCallback(async () => {
    ser(null); if (!user) { router.push('/signup?ref=follow-'+entityType+'-'+entityId); return; }
    sal(true);
    try {
      if (f) {
        if (aid) {
          const ar = await fetchWithAuth('/api/alerts/'+aid);
          if (ar.ok) { const aj = await ar.json(); const lst: string[] = aj[tf] ?? []; const rem = lst.filter(c => c !== entityCnpj);
            if (rem.length === 0) await fetchWithAuth('/api/alerts/'+aid, { method: 'DELETE' });
            else await fetchWithAuth('/api/alerts/'+aid, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [tf]: rem }) });
          }
        }
        safeTrack('entity_track_stopped', { entity_type: entityType, entity_id: entityId, entity_name: entityName, entity_cnpj: entityCnpj });
        if (mr.current) { sf(false); said(null); sal(false); }
      } else {
        const cr = await fetchWithAuth('/api/alerts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Monitoramento - '+entityName, filters: {}, [tf]: [entityCnpj] }) });
        if (!cr.ok) { const ed = await cr.json().catch(()=>null); const dt = ed?.detail ?? ed?.message ?? ''; if (dt.toLowerCase().includes('limite') || cr.status === 409) { if (mr.current) slr(true); throw new Error(dt || 'Limite'); } throw new Error(dt || 'Erro'); }
        const cj = await cr.json();
        safeTrack('entity_track_started', { entity_type: entityType, entity_id: entityId, entity_name: entityName, entity_cnpj: entityCnpj });
        if (mr.current) { sf(true); said(cj.id); slr(false); sal(false); }
      }
    } catch(e) { if (mr.current) { ser(e instanceof Error ? e.message : 'Erro'); sal(false); } }
  }, [user, f, aid, entityType, entityId, entityName, entityCnpj, tf, router]);
  useEffect(() => { return () => { mr.current = false; }; }, []);

  const Spinner = ({c}:{c?:string}) => <span className={'w-4 h-4 rounded-full border-2 border-t-transparent animate-spin shrink-0 '+(c||'')}/>;
  const Bell = ({fi}:{fi:boolean}) => <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill={fi?'currentColor':'none'} stroke="currentColor" strokeWidth={fi?0:2} className="w-4 h-4 shrink-0" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>;
  const Wrp = ({c,t}:{c:React.ReactNode;t:string}) => <span className="relative inline-block group">{c}<span role="tooltip" className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 text-xs text-white bg-gray-800 rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-lg z-50">{t}</span></span>;

  if (ck || authL) return <button type="button" disabled className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 bg-gray-50 text-gray-400 text-sm font-medium cursor-wait" aria-label="Verificando..."><Spinner c="border-gray-300"/><span>Verificando...</span></button>;
  if (lr && !f) return <Wrp c={<button type="button" disabled className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 bg-gray-50 text-gray-400 text-sm font-medium cursor-not-allowed" aria-label="Limite"><Bell fi={false}/><span>{fl}</span></button>} t={'Limite de '+(el==='orgao'?'orgaos':'fornecedores')+' monitorados atingido. Faca upgrade.'}/>;
  if (er) return <button type="button" onClick={()=>{ser(null);toggle()}} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm font-medium hover:bg-red-100" aria-label="Tentar"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 shrink-0" aria-hidden="true"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg><span>Tentar novamente</span></button>;
  if (f) return <Wrp c={<button type="button" onClick={toggle} disabled={al} className={'inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors '+(al?'border-gray-200 bg-gray-50 text-gray-400 cursor-wait':'border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100')} aria-label={al?'Removendo...':'Deixar de seguir '+el}>{al?<Spinner c="border-emerald-300"/>:<Bell fi/>}<span>{al?'Removendo...':'Seguindo'}</span></button>} t="Clique para deixar de seguir"/>;
  return <Wrp c={<button type="button" onClick={toggle} disabled={al} className={'inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors '+(al?'border-gray-200 bg-gray-50 text-gray-400 cursor-wait':'border-brand-blue text-brand-blue bg-white hover:bg-brand-blue hover:text-white')} aria-label={al?'Seguindo...':fl}>{al?<Spinner c="border-brand-blue"/>:<Bell fi={false}/>}<span>{al?'Seguindo...':fl}</span></button>} t={'Receba alertas quando '+(el==='orgao'?'este orgao':'este fornecedor')+' publicar novos editais'}/>;
}
