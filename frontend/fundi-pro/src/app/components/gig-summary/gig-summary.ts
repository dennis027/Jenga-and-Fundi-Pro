import { I18nService, TPipe } from '../../services/i18n';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { isoDate, saveBlob } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
type Tab = 'waiting' | 'ready' | 'completed';

@Component({
  selector: 'app-gig-summary',
  standalone: true,
  imports: [TPipe, CommonModule, FormsModule, RouterModule],
  templateUrl: './gig-summary.html',
  styleUrl: './gig-summary.css',
})
export class GigSummary implements OnInit {
  private i18n = inject(I18nService);
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  duration = (v: number, u: string) => this.i18n.t(u === 'weeks' ? (v === 1 ? '{0} week' : '{0} weeks') : (v === 1 ? '{0} day' : '{0} days'), v);
  @ViewChild('disputeDialog') disputeDialog?: ElementRef<HTMLDialogElement>;

  loading = signal(true);
  open = signal<any[]>([]);
  done = signal<any[]>([]);
  disputes = signal<any[]>([]);
  completedInfo = signal<any[]>([]);
  rating = signal<any | null>(null);
  stars = signal(0);
  paidOnTime = signal<boolean | null>(null);
  comment = signal('');
  stFrom = signal(isoDate(new Date(Date.now() - 90 * 86400000)));
  stTo = signal(isoDate(new Date()));
  statement = signal<any | null>(null);
  @ViewChild('rateDialog') rateDialogRef?: ElementRef<HTMLDialogElement>;
  @ViewChild('statementDialog') statementDialogRef?: ElementRef<HTMLDialogElement>;
  tab = signal<Tab>('waiting');
  q = signal('');
  completing = signal<number | null>(null);
  disputing = signal<{ kind: 'gig' | 'history'; row: any } | null>(null);
  reason = signal('');
  sending = signal(false);

  counts = computed(() => ({
    waiting: this.open().filter((g) => !g.is_verified).length,
    ready: this.open().filter((g) => g.is_verified).length,
    completed: this.done().length,
  }));
  rows = computed(() => {
    const q = this.q().toLowerCase();
    const list = this.tab() === 'completed' ? this.done() : this.open().filter((g) => (this.tab() === 'ready') === g.is_verified);
    return list.filter((g) => !q || `${g.job_type_name} ${g.organization_name}`.toLowerCase().includes(q))
      .sort((a, b) => b.start_date.localeCompare(a.start_date));
  });
  tabs: { id: Tab; label: string }[] = [
    { id: 'waiting', label: 'Waiting' }, { id: 'ready', label: 'Ready to complete' }, { id: 'completed', label: 'Completed' },
  ];

  ngOnInit() {
    this.appBar.setTitle('My gigs');
    this.appBar.setActions([{ id: 'refresh', icon: 'refresh', ariaLabel: 'Refresh', onClick: () => this.load() }]);
    const t = this.route.snapshot.queryParamMap.get('tab') as Tab | null;
    if (t && ['waiting', 'ready', 'completed'].includes(t)) this.tab.set(t);
    if (this.browser) this.load();
  }

  load() {
    forkJoin({
      open: this.http.get<any[]>(API + 'user-gigs/').pipe(catchError(() => of([]))),
      done: this.http.get<any[]>(API + 'user-work-history/').pipe(catchError(() => of([]))),
      disputes: this.http.get<any[]>(API + 'disputes/').pipe(catchError(() => of([]))),
      info: this.http.get<any[]>(API + 'fundi/completed/').pipe(catchError(() => of([]))),
    }).subscribe((r) => {
      this.open.set(r.open); this.done.set(r.done); this.disputes.set(r.disputes); this.completedInfo.set(r.info);
      if (!this.route.snapshot.queryParamMap.get('tab') && !r.open.some((g) => !g.is_verified) && r.open.some((g) => g.is_verified)) this.tab.set('ready');
      this.loading.set(false);
    });
  }

  siteRatingFor(historyId: number) {
    return this.completedInfo().find((h) => h.id === historyId)?.my_site_rating || null;
  }

  openRate(g: any) {
    this.rating.set(g); this.stars.set(0); this.paidOnTime.set(null); this.comment.set('');
    this.rateDialogRef?.nativeElement.showModal();
  }

  sendRating(dlg: HTMLDialogElement) {
    const g = this.rating(); if (!g || !this.stars()) return;
    this.sending.set(true);
    this.http.post<any>(API + `gig-history/${g.id}/rate-site/`, { stars: this.stars(), paid_on_time: this.paidOnTime(), comment: this.comment().trim() }).subscribe({
      next: (r) => {
        this.sending.set(false); dlg.close();
        this.completedInfo.update((l) => l.map((h) => (h.id === g.id ? { ...h, my_site_rating: r } : h)));
        this.snack.open(this.i18n.t('Thanks! Your rating helps other fundis.'), this.i18n.t('OK'), { duration: 3500, panelClass: 'success-snackbar' });
      },
      error: (e) => { this.sending.set(false); this.snack.open(e?.error?.detail || this.i18n.t('Could not send.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  openStatement() { this.statement.set(null); this.statementDialogRef?.nativeElement.showModal(); this.previewStatement(); }
  private stParams(extra: Record<string, string> = {}) { return { from: this.stFrom(), to: this.stTo(), ...extra }; }
  previewStatement() {
    this.http.get<any>(API + 'fundi/statement/', { params: this.stParams() }).subscribe({
      next: (s) => this.statement.set(s),
      error: (e) => this.snack.open(e?.error?.detail || this.i18n.t('Could not load.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }
  downloadStatement() {
    this.http.get(API + 'fundi/statement/', { params: this.stParams({ csv: '1' }), responseType: 'blob' }).subscribe({
      next: (b) => saveBlob(b, `fundi-statement_${this.stFrom()}_${this.stTo()}.csv`),
      error: () => this.snack.open(this.i18n.t('Could not download.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  disputeFor(kind: 'gig' | 'history', id: number) {
    return this.disputes().find((d) => d[kind] === id);
  }

  complete(g: any) {
    this.completing.set(g.id);
    this.http.post<any>(API + `gigs/${g.id}/complete/`, {}).subscribe({
      next: (res) => { this.completing.set(null); this.snack.open(this.i18n.t('Done! Your credit score is now {0}.', res.new_score), this.i18n.t('OK'), { duration: 3500, panelClass: 'success-snackbar' }); this.load(); },
      error: (e) => { this.completing.set(null); this.snack.open(e?.error?.error || this.i18n.t('Could not complete the gig.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  openDispute(kind: 'gig' | 'history', row: any) {
    this.disputing.set({ kind, row }); this.reason.set('');
    this.disputeDialog?.nativeElement.showModal();
  }
  closeDispute() { this.disputeDialog?.nativeElement.close(); }
  sendDispute() {
    const d = this.disputing(); if (!d || this.reason().trim().length < 10) return;
    this.sending.set(true);
    this.http.post<any>(API + 'disputes/', { [d.kind]: d.row.id, reason: this.reason().trim() }).subscribe({
      next: (res) => { this.sending.set(false); this.disputes.update((l) => [res, ...l]); this.closeDispute();
        this.snack.open(this.i18n.t('Dispute sent. Our team will review it and contact you.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'success-snackbar' }); },
      error: (e) => { this.sending.set(false); this.snack.open(e?.error?.detail || this.i18n.t('Could not send the dispute.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
