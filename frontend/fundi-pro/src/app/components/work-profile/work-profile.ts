import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, inject, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../../environments/environment';
import { I18nService, TPipe } from '../../services/i18n';

const TRADES = ['Masonry', 'Plumbing', 'Electrical', 'Carpentry', 'Tiling', 'Painting', 'Welding', 'Plastering', 'Roofing',
  'Steel fixing', 'Block laying', 'Concrete works', 'Landscaping', 'Glazing', 'General labour'];

@Component({
  selector: 'app-work-profile',
  standalone: true,
  imports: [FormsModule, TPipe],
  template: `
  <section class="panel">
    <div class="panel-head"><div><h2>{{ 'Work profile' | t }}</h2><p>{{ 'Contractors search for workers by trade and area. Your skills and rate show on your profile.' | t }}</p></div>
      <label class="avail" [class.on]="available()">
        <input type="checkbox" [ngModel]="available()" (ngModelChange)="available.set($event)">
        <span class="dot"></span> {{ (available() ? 'Available for work' : 'Busy') | t }}
      </label>
    </div>
    <div class="panel-body">
      <div class="field">
        <label>{{ 'My trades' | t }}</label>
        <div class="trades">
          @for (tr of trades; track tr) {
            <button type="button" class="trade" [class.on]="skills().includes(tr)" (click)="toggle(tr)">
              @if (skills().includes(tr)) { <span class="icon">check</span> } {{ tr | t }}</button>
          }
        </div>
      </div>
      <div class="form-grid">
        <div class="field"><label for="wp-years">{{ 'Years of experience' | t }}</label>
          <input id="wp-years" class="input" type="number" min="0" max="60" [ngModel]="years()" (ngModelChange)="years.set($event)"></div>
        <div class="field"><label for="wp-rate">{{ 'Usual day rate (KSh)' | t }}</label>
          <input id="wp-rate" class="input" type="number" min="0" step="50" [ngModel]="rate()" (ngModelChange)="rate.set($event)"></div>
        @if (!available()) {
          <div class="field full"><label for="wp-from">{{ 'Available again from' | t }}</label>
            <input id="wp-from" class="input" type="date" [ngModel]="from()" (ngModelChange)="from.set($event)"></div>
        }
        <div class="field full"><label for="wp-bio">{{ 'About my work' | t }}</label>
          <textarea id="wp-bio" class="input" rows="3" maxlength="500" [placeholder]="'e.g. Block work and plastering on multi-storey sites. Own tools.' | t"
                    [ngModel]="bio()" (ngModelChange)="bio.set($event)"></textarea></div>
      </div>
    </div>
    <div class="panel-foot">
      <button class="btn primary" type="button" (click)="save()" [disabled]="saving()"><span class="icon">save</span> {{ (saving() ? 'Saving…' : 'Save work profile') | t }}</button>
    </div>
  </section>`,
  styles: [`
    .panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap; }
    .trades { display: flex; flex-wrap: wrap; gap: 8px; }
    .trade { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--border); background: var(--surface); color: var(--text-2);
             border-radius: 999px; padding: 6px 12px; font: inherit; font-size: .86rem; cursor: pointer; }
    .trade .icon { font-size: 16px; }
    .trade.on { background: var(--primary-soft); color: var(--primary); border-color: var(--primary); font-weight: 600; }
    .avail { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 999px; background: var(--surface-2);
             font-size: .86rem; font-weight: 600; cursor: pointer; color: var(--muted); }
    .avail input { display: none; }
    .avail .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--faint); }
    .avail.on { background: var(--success-soft); color: var(--success); }
    .avail.on .dot { background: var(--success); }
    .form-grid { margin-top: 16px; }
  `],
})
export class WorkProfile implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private i18n = inject(I18nService);
  private api = environment.apiUrl + 'api/me/work-profile/';
  private platform = inject(PLATFORM_ID);
  trades = TRADES;
  skills = signal<string[]>([]);
  years = signal<number | null>(null);
  rate = signal<number | null>(null);
  bio = signal('');
  available = signal(true);
  from = signal<string | null>(null);
  saving = signal(false);

  ngOnInit() {
    if (!isPlatformBrowser(this.platform)) return;
    this.http.get<any>(this.api).subscribe((p) => {
      const list = (p.skills || '').split(',').map((s: string) => s.trim()).filter(Boolean);
      this.trades = [...TRADES, ...list.filter((s: string) => !TRADES.includes(s))];
      this.skills.set(list); this.years.set(p.years_experience); this.rate.set(p.day_rate);
      this.bio.set(p.bio || ''); this.available.set(p.is_available); this.from.set(p.available_from);
    });
  }

  toggle(t: string) { this.skills.update((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t])); }

  save() {
    this.saving.set(true);
    const n = (v: any) => (v === '' || v === null || v === undefined ? null : Number(v));
    this.http.patch(this.api, {
      skills: this.skills().join(', '), years_experience: n(this.years()), day_rate: n(this.rate()), bio: this.bio(),
      is_available: this.available(), available_from: this.available() ? null : (this.from() || null),
    }).subscribe({
      next: () => { this.saving.set(false); this.snack.open(this.i18n.t('Work profile saved.'), this.i18n.t('OK'), { duration: 3000, panelClass: 'success-snackbar' }); },
      error: (e) => {
        this.saving.set(false);
        const err = e?.error && typeof e.error === 'object' ? Object.values(e.error).flat()[0] : null;
        this.snack.open(String(err || this.i18n.t('Could not save.')), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' });
      },
    });
  }
}
