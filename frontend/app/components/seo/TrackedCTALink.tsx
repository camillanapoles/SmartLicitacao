"use client";
import Link from "next/link";
import { ComponentProps, ReactNode } from "react";

interface TrackedCTALinkProps extends Omit<ComponentProps<typeof Link>, "onClick"> {
  eventName: string;
  eventProps?: Record<string, unknown>;
  children: ReactNode;
}

export function TrackedCTALink({
  eventName,
  eventProps,
  children,
  ...linkProps
}: TrackedCTALinkProps) {
  const handleClick = () => {
    if (typeof window !== "undefined") {
      window.mixpanel?.track(eventName, eventProps);
    }
  };
  return (
    <Link {...linkProps} onClick={handleClick}>
      {children}
    </Link>
  );
}
