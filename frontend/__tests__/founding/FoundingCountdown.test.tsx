/**
 * BIZ-FOUND-002: tests for FoundingCountdown — seat counter + deadline countdown.
 */

import { render, screen, act } from '@testing-library/react';
import FoundingCountdown, {
  FoundingAvailabilitySnapshot,
} from '../../app/founding/components/FoundingCountdown';

function buildSnapshot(over: Partial<FoundingAvailabilitySnapshot> = {}): FoundingAvailabilitySnapshot {
  return {
    available: true,
    seats_total: 50,
    seats_remaining: 47,
    seats_taken: 3,
    deadline_at: '2026-05-30T23:59:59-03:00',
    paused: false,
    reason: 'available',
    coupon_code: 'FOUNDING_LIFETIME',
    discount_pct: 50,
    ...over,
  };
}

describe('FoundingCountdown', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    // Pin "now" to a known instant well before deadline so tests are stable.
    jest.setSystemTime(new Date('2026-04-28T10:00:00-03:00'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('renders loading placeholder when snapshot is null', () => {
    render(<FoundingCountdown snapshot={null} />);
    expect(screen.getByTestId('founding-availability-loading')).toBeInTheDocument();
  });

  it('renders X/50 seat counter when available', () => {
    render(<FoundingCountdown snapshot={buildSnapshot()} />);
    expect(screen.getByTestId('founding-seat-counter').textContent).toMatch(/47/);
    expect(screen.getByTestId('founding-seat-counter').textContent).toMatch(/50/);
    expect(screen.getByTestId('founding-discount-label').textContent).toMatch(/50%/);
  });

  it('shows program-closed message when not available', () => {
    render(
      <FoundingCountdown
        snapshot={buildSnapshot({ available: false, seats_remaining: 0, seats_taken: 50, reason: 'founding_cap_reached' })}
      />,
    );
    expect(screen.getByTestId('founding-seat-counter').textContent).toMatch(/programa fechado/i);
  });

  it('renders countdown days/hours/minutes/seconds', () => {
    render(<FoundingCountdown snapshot={buildSnapshot()} />);
    expect(screen.getByTestId('founding-countdown')).toBeInTheDocument();
    expect(screen.getByTestId('founding-countdown-days')).toBeInTheDocument();
    expect(screen.getByTestId('founding-countdown-hours')).toBeInTheDocument();
    expect(screen.getByTestId('founding-countdown-minutes')).toBeInTheDocument();
    expect(screen.getByTestId('founding-countdown-seconds')).toBeInTheDocument();
  });

  it('shows expired message when deadline passed', () => {
    jest.setSystemTime(new Date('2026-06-01T10:00:00-03:00'));
    render(<FoundingCountdown snapshot={buildSnapshot()} />);
    expect(screen.getByTestId('founding-countdown-expired')).toBeInTheDocument();
  });

  it('ticks the countdown every second', () => {
    render(<FoundingCountdown snapshot={buildSnapshot()} />);
    const beforeSeconds = screen.getByTestId('founding-countdown-seconds').textContent;
    act(() => {
      jest.advanceTimersByTime(1500);
    });
    const afterSeconds = screen.getByTestId('founding-countdown-seconds').textContent;
    expect(beforeSeconds).not.toBe(afterSeconds);
  });

  it('shows paused notice when paused=true', () => {
    render(<FoundingCountdown snapshot={buildSnapshot({ available: false, paused: true, reason: 'founding_paused' })} />);
    expect(screen.getByTestId('founding-paused-notice')).toBeInTheDocument();
  });

  it('renders urgency styling when seats_remaining <= 5', () => {
    const { container } = render(
      <FoundingCountdown snapshot={buildSnapshot({ seats_remaining: 3, seats_taken: 47 })} />,
    );
    expect(screen.getByTestId('founding-seat-counter').textContent).toMatch(/corra/i);
    expect(container.querySelector('.bg-amber-50')).not.toBeNull();
  });
});
