// Site safety: report injuries, near misses and hazards; site owners resolve them.
// Canonical: frontend/design-system/pages/safety.ts (copied to app/components/safety/ in both portals)
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { I18nService, TPipe } from '../../services/i18n';
import { isoDate } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
const KINDS = [
  { id: 'injury', label: 'Injury', icon: 'personal_injury' }, { id: 'near_miss', label: 'Near miss', icon: 'warning' },
  { id: 'hazard', label: 'Hazard', icon: 'report' }, { id: 'other', label: 'Other', icon: 'help' },
];

@Component({
  selector: 'app-safety',
  standalone: true,
  imports: [CommonModule, FormsModule, TPipe],
  template: `
<div class="page">
  <div class="page-head">
    <div><h1>{{ 'Site safety' | t }}</h1><p>{{ 'Report injuries, near misses and hazards. The site’s contractor is notified straight away.' | t }}</p></div>
    <div class="actions"><button class="btn primary" type="button" (click)="openReport()" [disabled]="!sites().length"><span class="icon">add</span> {{ 'Report an incident' | t }}</button></div>
  </div>

  <div class="stat-grid three">
    <div class="stat"><span class="tile pink"><span class="icon">health_and_safety</span></span><div><div class="label">{{ 'Open' | t }}</div><div class="value">{{ openCount() }}</div></div></div>
    <div class="stat"><span class="tile orange"><span class="icon">priority_high</span></span><div><div class="label">{{ 'High severity' | t }}</div><div class="value">{{ highCount() }}</div></div></div>
    <div class="stat"><span class="tile green"><span class="icon">task_alt</span></span><div><div class="label">{{ 'Resolved' | t }}</div><div class="value">{{ items().length - openCount() }}</div></div></div>
  </div>

  <div class="panel">
    <div class="toolbar">
      <div class="seg" role="tablist">
        <button type="button" [class.on]="filter() === 'open'" (click)="filter.set('open')">{{ 'Open' | t }} <span class="count">{{ openCount() }}</span></button>
        <button type="button" [class.on]="filter() === 'all'" (click)="filter.set('all')">{{ 'All' | t }} <span class="count">{{ items().length }}</span></button>
      </div>
    </div>
    @if (loading()) {
      <div class="panel-body"><div class="skeleton" style="height:160px"></div></div>
    } @else if (!shown().length) {
      <div class="empty"><span class="icon">health_and_safety</span><h3>{{ 'No incidents' | t }}</h3>
        <p>{{ (sites().length ? 'Nothing reported. Stay safe.' : 'You can report incidents at sites you have worked at.') | t }}</p></div>
    } @else {
      <div class="incidents">
        @for (i of shown(); track i.id) {
          <article class="incident" [class.resolved]="i.is_resolved">
            <span class="kind" [ngClass]="i.severity"><span class="icon">{{ icon(i.kind) }}</span></span>
            <div class="grow">
              <div class="top"><strong>{{ label(i.kind) | t }} · {{ i.site }}</strong>
                <span class="badge" [ngClass]="i.severity === 'high' ? 'danger' : i.severity === 'medium' ? 'warn' : ''">{{ sevLabel(i.severity) | t }}</span>
                @if (i.is_resolved) { <span class="badge ok">{{ 'Resolved' | t }}</span> }</div>
              <p>{{ i.description }}</p>
              <small class="muted">{{ i.occurred_on | date: 'd MMM y' }} · {{ 'Reported by {0}' | t : i.reported_by }}</small>
              @if (i.resolution) { <div class="resolution"><span class="icon">check_circle</span> {{ i.resolution }}</div> }
            </div>
            @if (!i.is_resolved && owned().has(i.organization)) {
              <button class="btn outline sm" type="button" (click)="openResolve(i)"><span class="icon">done</span> {{ 'Resolve' | t }}</button>
            }
          </article>
        }
      </div>
    }
  </div>
</div>

<dialog class="modal" #reportDlg>
  <div class="modal-head"><div><h2>{{ 'Report an incident' | t }}</h2><p>{{ 'Be specific: where, what happened, and anyone hurt.' | t }}</p></div>
    <button class="icon-btn" type="button" (click)="reportDlg.close()" [attr.aria-label]="'Close' | t"><span class="icon">close</span></button></div>
  <div class="modal-body">
    <div class="field"><label for="sf-site">{{ 'Site' | t }}</label>
      <select id="sf-site" class="input" [ngModel]="site()" (ngModelChange)="site.set(+$event)">
        @for (s of sites(); track s.id) { <option [value]="s.id">{{ s.name }}</option> }
      </select></div>
    <div class="field"><label>{{ 'What happened?' | t }}</label>
      <div class="kinds">
        @for (k of kinds; track k.id) {
          <button type="button" class="kind-btn" [class.on]="kind() === k.id" (click)="kind.set(k.id)"><span class="icon">{{ k.icon }}</span> {{ k.label | t }}</button>
        }
      </div></div>
    <div class="form-grid">
      <div class="field"><label>{{ 'How serious?' | t }}</label>
        <div class="seg">
          @for (s of ['low','medium','high']; track s) { <button type="button" [class.on]="severity() === s" (click)="severity.set(s)">{{ sevLabel(s) | t }}</button> }
        </div></div>
      <div class="field"><label for="sf-date">{{ 'When' | t }}</label>
        <input id="sf-date" class="input" type="date" [max]="today" [ngModel]="date()" (ngModelChange)="date.set($event)"></div>
    </div>
    <div class="field"><label for="sf-desc">{{ 'Description' | t }}</label>
      <textarea id="sf-desc" class="input" rows="4" maxlength="1000" [placeholder]="'e.g. Scaffold plank on floor 3 is loose. Nobody hurt.' | t"
                [ngModel]="desc()" (ngModelChange)="desc.set($event)"></textarea></div>
  </div>
  <div class="modal-foot">
    <button class="btn ghost" type="button" (click)="reportDlg.close()">{{ 'Cancel' | t }}</button>
    <button class="btn primary" type="button" (click)="report(reportDlg)" [disabled]="busy() || desc().trim().length < 10 || !kind()">{{ 'Send report' | t }}</button>
  </div>
</dialog>

<dialog class="modal" #resolveDlg>
  <div class="modal-head"><div><h2>{{ 'Resolve incident' | t }}</h2><p>{{ resolving()?.description }}</p></div>
    <button class="icon-btn" type="button" (click)="resolveDlg.close()" [attr.aria-label]="'Close' | t"><span class="icon">close</span></button></div>
  <div class="modal-body">
    <div class="field"><label for="sf-res">{{ 'What was done?' | t }}</label>
      <textarea id="sf-res" class="input" rows="3" maxlength="500" [ngModel]="resolution()" (ngModelChange)="resolution.set($event)"></textarea></div>
  </div>
  <div class="modal-foot">
    <button class="btn ghost" type="button" (click)="resolveDlg.close()">{{ 'Cancel' | t }}</button>
    <button class="btn primary" type="button" (click)="resolve(resolveDlg)" [disabled]="busy()">{{ 'Mark resolved' | t }}</button>
  </div>
</dialog>`,
  styles: [`
    .stat-grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: 20px; }
    @media (max-width: 700px) { .stat-grid.three { grid-template-columns: 1fr; } }
    .incidents { display: flex; flex-direction: column; }
    .incident { display: flex; gap: 14px; align-items: flex-start; padding: 16px 22px; border-top: 1px solid var(--border); }
    .incident.resolved { opacity: .75; }
    .incident .grow { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
    .incident .top { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .incident p { color: var(--text-2); }
    .kind { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; flex: none; background: var(--surface-2); color: var(--muted); }
    .kind.high { background: var(--danger-soft); color: var(--danger); }
    .kind.medium { background: var(--warning-soft); color: var(--warning); }
    .resolution { display: flex; gap: 6px; align-items: center; color: var(--success); font-size: .88rem; }
    .resolution .icon { font-size: 17px; }
    .kinds { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .kind-btn { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text); font: inherit; cursor: pointer; }
    .kind-btn.on { border-color: var(--primary); background: var(--primary-soft); color: var(--primary); font-weight: 600; }
    .actions { display: flex; gap: 8px; }
  `],
})
export class Safety implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private i18n = inject(I18nService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  @ViewChild('reportDlg') reportRef?: ElementRef<HTMLDialogElement>;
  @ViewChild('resolveDlg') resolveRef?: ElementRef<HTMLDialogElement>;
  kinds = KINDS;
  today = isoDate(new Date());

  loading = signal(true);
  busy = signal(false);
  items = signal<any[]>([]);
  sites = signal<{ id: number; name: string }[]>([]);
  owned = signal<Set<number>>(new Set());
  filter = signal<'open' | 'all'>('open');
  site = signal<number>(0);
  kind = signal('');
  severity = signal('low');
  date = signal(this.today);
  desc = signal('');
  resolving = signal<any | null>(null);
  resolution = signal('');

  openCount = computed(() => this.items().filter((i) => !i.is_resolved).length);
  highCount = computed(() => this.items().filter((i) => !i.is_resolved && i.severity === 'high').length);
  shown = computed(() => this.filter() === 'open' ? this.items().filter((i) => !i.is_resolved) : this.items());

  ngOnInit() {
    this.appBar.setTitle('Site safety');
    this.appBar.clearActions();
    if (this.browser) this.load();
  }

  load() {
    const list = (u: string) => this.http.get<any[]>(API + u).pipe(catchError(() => of([])));
    forkJoin({ incidents: list('incidents/'), mine: list('user-organizations/'), gigs: list('user-gigs/'), done: list('user-work-history/') })
      .subscribe((r) => {
        const map = new Map<number, string>();
        r.mine.forEach((o: any) => map.set(o.id, o.name));
        [...r.gigs, ...r.done].forEach((g: any) => g.organization && map.set(g.organization, g.organization_name || map.get(g.organization) || ''));
        this.sites.set([...map.entries()].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name)));
        this.owned.set(new Set(r.mine.map((o: any) => o.id)));
        this.items.set(r.incidents);
        this.loading.set(false);
      });
  }

  icon(k: string) { return KINDS.find((x) => x.id === k)?.icon || 'help'; }
  label(k: string) { return KINDS.find((x) => x.id === k)?.label || k; }
  sevLabel(s: string) { return ({ low: 'Low', medium: 'Medium', high: 'High' } as any)[s] || s; }

  openReport() {
    this.site.set(this.sites()[0]?.id || 0); this.kind.set(''); this.severity.set('low'); this.date.set(this.today); this.desc.set('');
    this.reportRef?.nativeElement.showModal();
  }

  report(dlg: HTMLDialogElement) {
    this.busy.set(true);
    this.http.post<any>(API + 'incidents/', { organization: this.site(), kind: this.kind(), severity: this.severity(),
      occurred_on: this.date(), description: this.desc().trim() }).subscribe({
      next: (i) => { this.busy.set(false); dlg.close(); this.items.update((l) => [i, ...l]);
        this.snack.open(this.i18n.t('Report sent to the site.'), this.i18n.t('OK'), { duration: 3500, panelClass: 'success-snackbar' }); },
      error: (e) => { this.busy.set(false); this.snack.open(e?.error?.detail || this.i18n.t('Could not send.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  openResolve(i: any) { this.resolving.set(i); this.resolution.set(''); this.resolveRef?.nativeElement.showModal(); }

  resolve(dlg: HTMLDialogElement) {
    const i = this.resolving(); if (!i) return;
    this.busy.set(true);
    this.http.post<any>(API + `incidents/${i.id}/resolve/`, { resolution: this.resolution().trim() }).subscribe({
      next: (r) => { this.busy.set(false); dlg.close(); this.items.update((l) => l.map((x) => (x.id === r.id ? r : x))); },
      error: (e) => { this.busy.set(false); this.snack.open(e?.error?.detail || this.i18n.t('Could not save.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
