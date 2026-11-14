// Runtime translations. English text is the key, so a missing translation falls back to
// English instead of showing a blank. Canonical copy: frontend/design-system/i18n.ts
import { Injectable, PLATFORM_ID, Pipe, PipeTransform, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { LANGUAGES, TRANSLATIONS } from '../shell/i18n-dict';

@Injectable({ providedIn: 'root' })
export class I18nService {
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  languages = LANGUAGES;
  lang = signal<string>('en');

  constructor() {
    if (!this.browser) return;
    try { const l = localStorage.getItem('lang'); if (l && LANGUAGES.some((x) => x.code === l)) this.lang.set(l); } catch {}
    document.documentElement.lang = this.lang();
  }

  set(code: string) {
    this.lang.set(code);
    try { localStorage.setItem('lang', code); } catch {}
    if (this.browser) document.documentElement.lang = code;
  }

  /** Translate `text`; {0}, {1}… are replaced by `args`. */
  t(text: string, ...args: unknown[]): string {
    const table = TRANSLATIONS[this.lang()];
    let out = (table && table[text]) || text;
    args.forEach((a, i) => (out = out.split(`{${i}}`).join(String(a ?? ''))));
    return out;
  }
}

@Pipe({ name: 't', standalone: true, pure: false })
export class TPipe implements PipeTransform {
  private i18n = inject(I18nService);
  transform(text: string, ...args: unknown[]): string { return this.i18n.t(text, ...args); }
}
