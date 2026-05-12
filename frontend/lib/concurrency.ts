/**
 * ConcurrencyLimiter — Promise-based semaphore for limiting concurrent backend
 * requests during SSG/ISR build time.
 *
 * Memory: feedback_build_hammers_backend_cascade
 *   SSG (4146 pages) satura backend hobby DB pool quando centenas de fetches
 *   disparam simultaneamente durante "next build". Este semáforo serializa
 *   as requests no lado do cliente para não estourar o pool de conexões do
 *   backend Supabase (tipicamente 15-25 conexões concorrentes).
 *
 * Uso:
 *   import { ssgFetchLimiter } from '@/lib/concurrency';
 *   const resp = await ssgFetchLimiter.run(() => fetch(url, options));
 */
export class ConcurrencyLimiter {
  private maxConcurrent: number;
  private active: number;
  private queue: Array<{
    fn: () => Promise<unknown>;
    resolve: (v: unknown) => void;
    reject: (e: unknown) => void;
  }>;

  constructor(maxConcurrent: number = 6) {
    if (maxConcurrent < 1) throw new Error('maxConcurrent must be >= 1');
    this.maxConcurrent = maxConcurrent;
    this.active = 0;
    this.queue = [];
  }

  /**
   * Run a function through the concurrency semaphore.
   * Returns the function's result when a slot becomes available.
   */
  async run<T>(fn: () => Promise<T>): Promise<T> {
    if (this.active < this.maxConcurrent) {
      return this.execute(fn);
    }
    return new Promise<T>((resolve, reject) => {
      this.queue.push({
        fn: fn as () => Promise<unknown>,
        resolve: resolve as (v: unknown) => void,
        reject,
      });
    });
  }

  private async execute<T>(fn: () => Promise<T>): Promise<T> {
    this.active++;
    try {
      return await fn();
    } finally {
      this.active--;
      this.drain();
    }
  }

  private drain(): void {
    while (this.active < this.maxConcurrent && this.queue.length > 0) {
      const next = this.queue.shift()!;
      this.execute(next.fn).then(next.resolve).catch(next.reject);
    }
  }

  /** Current number of active (in-flight) operations. */
  get activeCount(): number {
    return this.active;
  }

  /** Current queue depth (waiting operations). */
  get queueDepth(): number {
    return this.queue.length;
  }
}

/**
 * Shared instance for SSG/ISR build fetches.
 * Max 6 concurrent backend requests — suficiente para manter throughput sem
 * estourar o pool de conexões do backend (Supabase hobby: 15 conexões).
 *
 * Páginas com generateStaticParams que disparam fetch() durante "next build"
 * DEVEM usar este mesmo semáforo para evitar o cascade de timeout descrito
 * em feedback_build_hammers_backend_cascade.
 */
export const ssgFetchLimiter = new ConcurrencyLimiter(6);

/**
 * Convenience wrapper: fetch() throttled by the shared SSG semaphore.
 *
 * Aceita mesmos argumentos de fetch(), adiciona AbortSignal.timeout se não
 * houver signal definido, e retorna a Response (ou lança exceção em caso de
 * erro de rede/timeout, igual ao fetch original).
 *
 * Uso:
 *   import { ssgLimitedFetch } from '@/lib/concurrency';
 *   const resp = await ssgLimitedFetch(url, { next: { revalidate: 3600 } });
 */
export async function ssgLimitedFetch(
  url: string,
  init?: RequestInit & { next?: { revalidate?: number } },
): Promise<Response> {
  return ssgFetchLimiter.run<Response>(async () => {
    const options: RequestInit & { next?: { revalidate?: number } } = {
      signal: init?.signal ?? AbortSignal.timeout(30_000),
      ...init,
    };
    return fetch(url, options);
  });
}
