/**
 * STORY-431 AC12: Empty-period CTA for the Observatory monthly report.
 *
 * Rendered when total_editais === 0 (historical month with no data ingested
 * or backend timeout fallback). Replaces the misleading "R$ 0,00" cards that
 * GSC was indexing as Soft 404s.
 */

type Props = {
  message: string;
  actionHref: string;
  actionLabel: string;
};

export function EmptyStatePeriod({ message, actionHref, actionLabel }: Props) {
  return (
    <div className="mb-10 rounded-lg border border-zinc-200 bg-zinc-50 p-8 text-center">
      <p className="text-zinc-600">{message}</p>
      <a
        href={actionHref}
        className="mt-4 inline-block text-blue-600 hover:underline"
      >
        {actionLabel} →
      </a>
    </div>
  );
}
