// Light / dark / system theme. Canonical copy: frontend/design-system/theme.ts
import { Injectable, PLATFORM_ID, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export type ThemeMode = 'light' | 'dark' | 'system';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  mode = signal<ThemeMode>('system');
  dark = signal(false);

  constructor() {
    if (!this.browser) return;
    let saved: ThemeMode = 'system';
    try { saved = (localStorage.getItem('theme') as ThemeMode) || 'system'; } catch {}
    this.mode.set(saved);
    this.apply();
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => this.apply());
  }

  set(mode: ThemeMode) {
    this.mode.set(mode);
    try { localStorage.setItem('theme', mode); } catch {}
    this.apply();
  }

  toggle() {
    this.set(this.dark() ? 'light' : 'dark');
  }

  private apply() {
    if (!this.browser) return;
    const m = this.mode();
    const dark = m === 'dark' || (m === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    this.dark.set(dark);
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  }
}
