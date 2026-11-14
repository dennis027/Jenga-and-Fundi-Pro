// Currently selected context (e.g. contractor site). Canonical: frontend/design-system/shell/
import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

@Injectable({ providedIn: 'root' })
export class SiteContextService {
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  id = signal<number | null>(null);
  label = signal('All sites');

  constructor() {
    if (!this.browser) return;
    try {
      const raw = localStorage.getItem('context');
      if (raw) { const c = JSON.parse(raw); this.id.set(c.id); this.label.set(c.label); }
    } catch {}
  }

  select(id: number | null, label: string) {
    this.id.set(id);
    this.label.set(label);
    try { localStorage.setItem('context', JSON.stringify({ id, label })); } catch {}
  }
}
