"use client";

import {useEffect, useRef} from "react";
import type {LucideIcon} from "lucide-react";

export type DockItem<T extends string> = {
  id: T;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
};

export function wrappedDockScrollLeft(current: number, segmentWidth: number): number {
  if (segmentWidth <= 0) return current;
  if (current >= segmentWidth * 2) return current - segmentWidth;
  if (current < segmentWidth) return current + segmentWidth;
  return current;
}

export function InfiniteDock<T extends string>({
  items,
  activeId,
  onSelect,
}: {
  items: DockItem<T>[];
  activeId: T;
  onSelect: (id: T) => void;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const movedRef = useRef(false);
  const startXRef = useRef(0);
  const startScrollRef = useRef(0);

  useEffect(() => {
    const viewport = viewportRef.current;
    const track = trackRef.current;
    if (!viewport || !track) return;

    let cancelled = false;
    let frame = 0;
    const settle = () => {
      if (cancelled) return;
      const segmentWidth = track.scrollWidth / 3;
      if (segmentWidth > 0) {
        viewport.scrollLeft = segmentWidth;
        return;
      }
      if (frame++ < 7) requestAnimationFrame(settle);
    };
    requestAnimationFrame(settle);

    let wrapping = false;
    const handleScroll = () => {
      if (wrapping) return;
      const segmentWidth = track.scrollWidth / 3;
      const next = wrappedDockScrollLeft(viewport.scrollLeft, segmentWidth);
      if (next === viewport.scrollLeft) return;
      wrapping = true;
      viewport.scrollLeft = next;
      requestAnimationFrame(() => { wrapping = false; });
    };
    viewport.addEventListener("scroll", handleScroll, {passive: true});
    return () => {
      cancelled = true;
      viewport.removeEventListener("scroll", handleScroll);
    };
  }, [items.length]);

  function finishDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    window.setTimeout(() => { movedRef.current = false; }, 0);
  }

  function moveFocus(event: React.KeyboardEvent<HTMLElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>(
      '[data-dock-copy="primary"] button',
    )];
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (current < 0) return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    buttons[(current + direction + buttons.length) % buttons.length]?.focus();
  }

  return (
    <nav className="dock infinite-dock" aria-label="Command Center surfaces" onKeyDown={moveFocus}>
      <div
        className="dock-viewport"
        ref={viewportRef}
        onPointerDown={(event) => {
          if (event.pointerType === "mouse" && event.button !== 0) return;
          draggingRef.current = true;
          movedRef.current = false;
          startXRef.current = event.clientX;
          startScrollRef.current = event.currentTarget.scrollLeft;
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!draggingRef.current) return;
          const distance = event.clientX - startXRef.current;
          if (Math.abs(distance) > 5) movedRef.current = true;
          event.currentTarget.scrollLeft = startScrollRef.current - distance * 1.25;
        }}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
      >
        <div className="dock-track" ref={trackRef}>
          {(["before", "primary", "after"] as const).map((copy) => (
            <div
              className="dock-copy"
              data-dock-copy={copy}
              key={copy}
              aria-hidden={copy === "primary" ? undefined : true}
            >
              {items.map(({id, label, shortLabel, icon: Icon}) => (
                <button
                  key={`${copy}-${id}`}
                  className={activeId === id ? "active" : ""}
                  tabIndex={copy === "primary" ? 0 : -1}
                  aria-current={copy === "primary" && activeId === id ? "page" : undefined}
                  aria-label={copy === "primary" ? label : undefined}
                  title={label}
                  onClick={(event) => {
                    if (movedRef.current) {
                      event.preventDefault();
                      return;
                    }
                    onSelect(id);
                  }}
                >
                  <span className="dock-icon"><Icon /></span>
                  <span className="dock-label-full">{label}</span>
                  <span className="dock-label-short">{shortLabel}</span>
                  <i aria-hidden="true" />
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </nav>
  );
}
