/**
 * CONV-INST-002: Device type helper.
 * Derives device category from viewport width for analytics segmentation.
 */

export type DeviceType = "mobile" | "tablet" | "desktop";

/**
 * Derive device type from a viewport width value.
 * Breakpoints mirror Tailwind defaults (sm=640, md=768, lg=1024).
 *   mobile  — < 768px
 *   tablet  — 768px – 1023px
 *   desktop — >= 1024px
 */
export function getDeviceType(width: number): DeviceType {
  if (width < 768) return "mobile";
  if (width < 1024) return "tablet";
  return "desktop";
}

/**
 * Read current device type from window.innerWidth.
 * Returns 'desktop' on SSR (window unavailable).
 */
export function currentDeviceType(): DeviceType {
  if (typeof window === "undefined") return "desktop";
  return getDeviceType(window.innerWidth);
}
