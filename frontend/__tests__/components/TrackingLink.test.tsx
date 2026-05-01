import { render, screen, fireEvent } from '@testing-library/react';
import TrackingLink from '@/components/TrackingLink';

const mockTrackEvent = jest.fn();
jest.mock('@/hooks/useAnalytics', () => ({
  useAnalytics: () => ({ trackEvent: mockTrackEvent }),
}));

jest.mock('next/link', () => {
  const MockLink = ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  );
  MockLink.displayName = 'MockLink';
  return MockLink;
});

describe('TrackingLink', () => {
  beforeEach(() => mockTrackEvent.mockClear());

  it('renders children with correct href', () => {
    render(
      <TrackingLink href="/signup?utm_campaign=test" eventName="cta_clicked">
        Teste grátis
      </TrackingLink>
    );
    const link = screen.getByRole('link', { name: /Teste grátis/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/signup?utm_campaign=test');
  });

  it('calls trackEvent on click with eventProps', () => {
    render(
      <TrackingLink
        href="/signup"
        eventName="cta_clicked"
        eventProps={{ cta_name: 'hero', page_type: 'test' }}
      >
        CTA
      </TrackingLink>
    );
    fireEvent.click(screen.getByRole('link'));
    expect(mockTrackEvent).toHaveBeenCalledWith('cta_clicked', { cta_name: 'hero', page_type: 'test' });
  });

  it('calls trackEvent with empty object when no eventProps', () => {
    render(
      <TrackingLink href="/signup" eventName="cta_clicked">CTA</TrackingLink>
    );
    fireEvent.click(screen.getByRole('link'));
    expect(mockTrackEvent).toHaveBeenCalledWith('cta_clicked', {});
  });
});
