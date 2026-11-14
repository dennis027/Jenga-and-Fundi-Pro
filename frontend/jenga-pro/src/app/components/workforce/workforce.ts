import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';
import { isoDate, saveBlob } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
type Tab = 'payroll' | 'attendance' | 'budgets' | 'ratings';

@Component({
  selector: 'app-workforce',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
<div class="page">
  <div class="page-head">
    <div><h1>Payroll &amp; attendance</h1><p>Who was on site, what you agreed to pay them, and how each site is tracking against its labour budget.</p></div>
  </div>

  <div class="panel">
    <div class="toolbar">
      <div class="seg" role="tablist">
        <button type="button" [class.on]="tab() === 'payroll'" (click)="go('payroll')">Payroll</button>
        <button type="button" [class.on]="tab() === 'attendance'" (click)="go('attendance')">Attendance</button>
        <button type="button" [class.on]="tab() === 'budgets'" (click)="go('budgets')">Budgets</button>
        <button type="button" [class.on]="tab() === 'ratings'" (click)="go('ratings')">Site ratings</button>
      </div>
      @if (tab() === 'payroll' || tab() === 'attendance') {
        <div class="range">
          <div class="seg">
            <button type="button" (click)="preset(7)" [class.on]="days() === 7">7 days</button>
            <button type="button" (click)="preset(14)" [class.on]="days() === 14">14 days</button>
            <button type="button" (click)="preset(30)" [class.on]="days() === 30">30 days</button>
          </div>
          <input class="input date" type="date" [ngModel]="from()" (ngModelChange)="from.set($event); days.set(0); load()" aria-label="From">
          <span class="muted">to</span>
          <input class="input date" type="date" [ngModel]="to()" (ngModelChange)="to.set($event); days.set(0); load()" aria-label="To">
          <button class="btn outline sm" type="button" (click)="csv()"><span class="icon">download</span> CSV</button>
        </div>
      }
    </div>

    @if (loading()) {
      <div class="panel-body"><div class="skeleton" style="height:200px"></div></div>
    } @else {
      @switch (tab()) {
        @case ('payroll') {
          <div class="summary">
            <div><small>Workers</small><strong>{{ payroll()?.rows.length || 0 }}</strong></div>
            <div><small>Gig days</small><strong>{{ totalGigDays() }}</strong></div>
            <div><small>Days checked in</small><strong>{{ totalCheckIns() }}</strong></div>
            <div><small>Agreed pay</small><strong>KSh {{ +(payroll()?.total || 0) | number: '1.0-0' }}</strong></div>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Worker</th><th>Site</th><th class="right">Gigs</th><th class="right">Gig days</th><th class="right">Checked in</th><th class="right">Agreed pay (KSh)</th><th></th></tr></thead>
              <tbody>
                @for (r of payrollRows(); track r.username + r.site) {
                  <tr>
                    <td><div class="cell-main">{{ r.worker }}</div><div class="cell-sub">{{ r.phone || '@' + r.username }}</div></td>
                    <td>{{ r.site }}</td>
                    <td class="right num">{{ r.gigs }}</td>
                    <td class="right num">{{ r.gig_days }}</td>
                    <td class="right num" [class.warn-text]="r.gig_days && r.days_on_site < r.gig_days">{{ r.days_on_site }}</td>
                    <td class="right num">{{ +r.agreed_pay | number: '1.2-2' }}</td>
                    <td>@if (!r.verified) { <span class="badge warn" title="Some gigs are not verified yet">Unverified</span> }</td>
                  </tr>
                } @empty {
                  <tr><td colspan="7"><div class="empty"><span class="icon">payments</span><h3>No work in this period</h3><p>Gigs that start in the selected dates appear here.</p></div></td></tr>
                }
              </tbody>
            </table>
          </div>
          <p class="foot-note muted">Agreed pay is from gigs that start in the period. “Checked in” counts days the worker confirmed being on site; amber means fewer check-ins than gig days.</p>
        }
        @case ('attendance') {
          <div class="summary">
            <div><small>Workers</small><strong>{{ attendance()?.workers || 0 }}</strong></div>
            <div><small>Worker-days</small><strong>{{ attendance()?.worker_days || 0 }}</strong></div>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Date</th><th>Worker</th><th>Site</th><th>Trade</th><th>Checked in</th></tr></thead>
              <tbody>
                @for (r of attendanceRows(); track $index) {
                  <tr><td class="nowrap">{{ r.date | date: 'EEE d MMM' }}</td><td class="cell-main">{{ r.worker }}</td><td>{{ r.site }}</td><td>{{ r.trade }}</td><td class="num">{{ r.checked_in_at }}</td></tr>
                } @empty {
                  <tr><td colspan="5"><div class="empty"><span class="icon">location_on</span><h3>No check-ins</h3><p>Fundis check in from their dashboard on days they're on site.</p></div></td></tr>
                }
              </tbody>
            </table>
          </div>
        }
        @case ('budgets') {
          <div class="budgets">
            @for (b of budgets(); track b.organization) {
              <div class="budget">
                <div class="b-head"><strong>{{ b.name }}</strong>@if (!b.is_active) { <span class="badge">Inactive</span> }</div>
                @if (b.budget !== null) {
                  <div class="progress" [class.over]="b.pct > 100"><span [style.width.%]="b.pct > 100 ? 100 : b.pct"></span></div>
                  <div class="b-nums"><span>KSh {{ +b.spent | number: '1.0-0' }} of {{ +b.budget | number: '1.0-0' }}</span>
                    <strong [class.danger-text]="b.pct > 100" [class.warn-text]="b.pct > 85 && b.pct <= 100">{{ b.pct }}%</strong></div>
                  <div class="muted small">Open gigs KSh {{ +b.committed_open | number: '1.0-0' }} · completed KSh {{ +b.paid_completed | number: '1.0-0' }}</div>
                } @else {
                  <div class="muted small">Agreed pay so far: KSh {{ +b.spent | number: '1.0-0' }}. No budget set.</div>
                }
                <div class="b-edit">
                  <input class="input" type="number" min="0" step="1000" placeholder="Labour budget (KSh)" [ngModel]="edit()[b.organization] ?? b.budget" (ngModelChange)="setEdit(b.organization, $event)">
                  <button class="btn outline sm" type="button" (click)="saveBudget(b.organization)">Save</button>
                </div>
              </div>
            } @empty {
              <div class="empty"><span class="icon">apartment</span><p>Add a site to track its labour budget.</p></div>
            }
          </div>
        }
        @case ('ratings') {
          <div class="budgets">
            @for (r of ratings(); track r.organization) {
              <div class="budget">
                <div class="b-head"><strong>{{ r.name }}</strong>
                  @if (r.avg) { <span class="stars-v"><span class="icon fill">star</span> {{ r.avg }} <small class="muted">({{ r.count }})</small></span> }</div>
                @if (r.paid_on_time_pct !== null) { <div class="muted small">Paid on time: <strong>{{ r.paid_on_time_pct }}%</strong> of workers who answered</div> }
                @for (x of r.recent; track $index) {
                  <div class="review"><span class="stars-v"><span class="icon fill">star</span> {{ x.stars }}</span> <span class="muted small">{{ x.by }} · {{ x.created_at | date: 'd MMM' }}</span>
                    @if (x.comment) { <p>“{{ x.comment }}”</p> }</div>
                } @empty { <p class="muted small">No ratings yet. Workers rate a site after a gig is completed.</p> }
              </div>
            }
          </div>
        }
      }
    }
  </div>
</div>`,
  styles: [`
    .toolbar { flex-wrap: wrap; gap: 12px; }
    .range { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .input.date { width: 150px; height: 36px; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; padding: 18px 22px 4px; }
    .summary div { background: var(--surface-2); border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; }
    .summary small { color: var(--muted); font-size: .8rem; }
    .summary strong { font-size: 1.25rem; }
    .foot-note { padding: 10px 22px 18px; font-size: .82rem; }
    .warn-text { color: var(--warning); font-weight: 600; }
    .danger-text { color: var(--danger); }
    .budgets { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; padding: 18px 22px 22px; }
    .budgets .empty { grid-column: 1 / -1; }
    .budget { border: 1px solid var(--border); border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
    .b-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .b-nums { display: flex; justify-content: space-between; font-size: .9rem; }
    .progress { height: 8px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
    .progress span { display: block; height: 100%; background: var(--primary); border-radius: 99px; }
    .progress.over span { background: var(--danger); }
    .b-edit { display: flex; gap: 8px; }
    .b-edit .input { height: 34px; }
    .stars-v { color: #f59e0b; font-weight: 600; display: inline-flex; align-items: center; gap: 2px; }
    .stars-v .icon { font-size: 17px; }
    .review { border-top: 1px solid var(--border); padding-top: 8px; }
    .review p { color: var(--text-2); font-size: .9rem; margin-top: 2px; }
    .small { font-size: .82rem; }
  `],
})
export class Workforce implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  ctx = inject(SiteContextService);

  tab = signal<Tab>('payroll');
  loading = signal(true);
  days = signal(7);
  from = signal(isoDate(new Date(Date.now() - 6 * 86400000)));
  to = signal(isoDate(new Date()));
  payroll = signal<any | null>(null);
  attendance = signal<any | null>(null);
  budgets = signal<any[]>([]);
  ratings = signal<any[]>([]);
  edit = signal<Record<number, any>>({});

  private bySite = (rows: any[]) => rows.filter((r) => this.ctx.id() === null || r.organization === this.ctx.id() || r.site === this.ctx.label());
  payrollRows = computed(() => this.bySite(this.payroll()?.rows || []));
  attendanceRows = computed(() => (this.attendance()?.rows || []).filter((r: any) => this.ctx.id() === null || r.site === this.ctx.label()));
  totalGigDays = computed(() => this.payrollRows().reduce((s: number, r: any) => s + r.gig_days, 0));
  totalCheckIns = computed(() => this.payrollRows().reduce((s: number, r: any) => s + r.days_on_site, 0));

  ngOnInit() {
    this.appBar.setTitle('Payroll & attendance');
    this.appBar.clearActions();
    const t = this.route.snapshot.queryParamMap.get('tab') as Tab | null;
    if (t && ['payroll', 'attendance', 'budgets', 'ratings'].includes(t)) this.tab.set(t);
    if (this.browser) this.load();
  }

  go(t: Tab) { this.tab.set(t); this.router.navigate([], { queryParams: { tab: t }, replaceUrl: true }); this.load(); }
  preset(n: number) { this.days.set(n); this.from.set(isoDate(new Date(Date.now() - (n - 1) * 86400000))); this.to.set(isoDate(new Date())); this.load(); }
  private params(extra: Record<string, string> = {}) { return { from: this.from(), to: this.to(), ...extra }; }

  load() {
    this.loading.set(true);
    const done = () => this.loading.set(false);
    const fail = (e: any) => { done(); this.snack.open(e?.error?.detail || 'Could not load.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); };
    switch (this.tab()) {
      case 'payroll': this.http.get<any>(API + 'contractor/payroll/', { params: this.params() }).subscribe({ next: (r) => { this.payroll.set(r); done(); }, error: fail }); break;
      case 'attendance': this.http.get<any>(API + 'contractor/attendance/', { params: this.params() }).subscribe({ next: (r) => { this.attendance.set(r); done(); }, error: fail }); break;
      case 'budgets': this.http.get<any[]>(API + 'contractor/budgets/').subscribe({ next: (r) => { this.budgets.set(r); done(); }, error: fail }); break;
      case 'ratings': this.http.get<any[]>(API + 'contractor/site-ratings/').subscribe({ next: (r) => { this.ratings.set(r); done(); }, error: fail }); break;
    }
  }

  csv() {
    const url = this.tab() === 'payroll' ? 'contractor/payroll/' : 'contractor/attendance/';
    const extra: Record<string, string> = { csv: '1' };
    if (this.ctx.id() !== null) extra['org'] = String(this.ctx.id());
    this.http.get(API + url, { params: this.params(extra), responseType: 'blob' }).subscribe({
      next: (b) => saveBlob(b, `${this.tab()}_${this.from()}_${this.to()}.csv`),
      error: () => this.snack.open('Could not download.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  setEdit(org: number, v: any) { this.edit.update((e) => ({ ...e, [org]: v })); }

  saveBudget(org: number) {
    const v = this.edit()[org];
    this.http.post<any>(API + 'contractor/budgets/', { organization: org, labour_budget: v === null || v === undefined ? '' : v }).subscribe({
      next: () => { this.snack.open('Budget saved.', 'OK', { duration: 2500, panelClass: 'success-snackbar' }); this.load(); },
      error: (e) => this.snack.open(e?.error?.detail || 'Could not save.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }
}
