/**
 * CONV-INST-002: Unit tests for device-type helper.
 * Covers all three breakpoint categories (mobile / tablet / desktop).
 */
/** @jest-environment jsdom */

import { getDeviceType, currentDeviceType } from "../../lib/device-type";

describe("getDeviceType", () => {
  it("returns 'mobile' for width < 768", () => {
    expect(getDeviceType(0)).toBe("mobile");
    expect(getDeviceType(320)).toBe("mobile");
    expect(getDeviceType(767)).toBe("mobile");
  });

  it("returns 'tablet' for width 768–1023", () => {
    expect(getDeviceType(768)).toBe("tablet");
    expect(getDeviceType(900)).toBe("tablet");
    expect(getDeviceType(1023)).toBe("tablet");
  });

  it("returns 'desktop' for width >= 1024", () => {
    expect(getDeviceType(1024)).toBe("desktop");
    expect(getDeviceType(1280)).toBe("desktop");
    expect(getDeviceType(1920)).toBe("desktop");
  });

  it("handles exact breakpoint boundaries correctly", () => {
    // 767 → mobile, 768 → tablet (not mobile)
    expect(getDeviceType(767)).toBe("mobile");
    expect(getDeviceType(768)).toBe("tablet");
    // 1023 → tablet, 1024 → desktop
    expect(getDeviceType(1023)).toBe("tablet");
    expect(getDeviceType(1024)).toBe("desktop");
  });
});

describe("currentDeviceType", () => {
  it("returns 'desktop' when window is undefined (SSR guard)", () => {
    const originalWindow = global.window;
    // @ts-expect-error simulate SSR
    delete global.window;
    expect(currentDeviceType()).toBe("desktop");
    global.window = originalWindow;
  });

  it("derives device type from window.innerWidth", () => {
    Object.defineProperty(window, "innerWidth", { writable: true, configurable: true, value: 375 });
    expect(currentDeviceType()).toBe("mobile");

    Object.defineProperty(window, "innerWidth", { writable: true, configurable: true, value: 800 });
    expect(currentDeviceType()).toBe("tablet");

    Object.defineProperty(window, "innerWidth", { writable: true, configurable: true, value: 1440 });
    expect(currentDeviceType()).toBe("desktop");
  });
});
