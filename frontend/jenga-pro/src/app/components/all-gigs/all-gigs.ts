import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnDestroy, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';
import { downloadCsv, duration, initials } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
type Tab = 'all' | 'pending' | 'verified' | 'completed';

interface Row {
  key: string; id: number; worker_name: string; job_type_name: string; organization: number; organization_name: string;
  start_date: string; duration_value: number; duration_unit: string; amount: number | null;
  status: 'pending' | 'verified' | 'completed'; rating: { stars: number; comment: string } | null;
}

@Component({
  selector: 'app-all-gigs',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './all-gigs.html',
  styleUrl: './all-gigs.css',
})
export class AllGigs implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  site = inject(SiteContextService);
  initials = initials; duration = duration;
  @ViewChild('rateDialog') rateDialog?: ElementRef<HTMLDialogElement>;

  loading = signal(true);
  rows = signal<Row[]>([]);
  tab = signal<Tab>('all');
  q = signal('');
  rating = signal<Row | null>(null);
  stars = signal(0);
  comment = signal('');
  saving = signal(false);

  inSite = computed(() => this.rows().filter((r) => this.site.id() === null || r.organization === this.site.id()));
  counts = computed(() => {
    const c = { all: 0, pending: 0, verified: 0, completed: 0 } as Record<Tab, number>;
    this.inSite().forEach((r) => { c.all++; c[r.status]++; });
    return c;
  });
  shown = computed(() => {
    const q = this.q().toLowerCase();
    return this.inSite()
      .filter((r) => this.tab() === 'all' || r.status === this.tab())
      .filter((r) => !q || `${r.worker_name} ${r.job_type_name} ${r.organization_name}`.toLowerCase().includes(q));
  });
  tabs: { id: Tab; label: string }[] = [
    { id: 'all', label: 'All' }, { id: 'pending', label: 'Pending' },
    { id: 'verified', label: 'In progress' }, { id: 'completed', label: 'Completed' },
  ];

  ngOnInit() {
    this.appBar.setTitle('All gigs');
    this.appBar.setActions([{ id: 'refresh', icon: 'refresh', ariaLabel: 'Refresh', onClick: () => this.load() }]);
    if (this.browser) this.load();
  }
  ngOnDestroy() { this.appBar.clearActions(); }

  load() {
    this.loading.set(true);
    forkJoin({
      open: this.http.get<any[]>(API + 'org-gigs-list/').pipe(catchError(() => of([]))),
      done: this.http.get<any[]>(API + 'contractor/completed-gigs/').pipe(catchError(() => of([]))),
    }).subscribe(({ open, done }) => {
      const a: Row[] = open.map((g) => ({
        key: 'g' + g.id, id: g.id, worker_name: g.worker_name, job_type_name: g.job_type_name, organization: g.organization,
        organization_name: g.organization_name, start_date: g.start_date, duration_value: g.duration_value,
        duration_unit: g.duration_unit, amount: Number(g.amount_paid), status: g.is_verified ? 'verified' : 'pending', rating: null,
      }));
      const b: Row[] = done.map((h) => ({
        key: 'h' + h.id, id: h.id, worker_name: h.worker_name, job_type_name: h.job_type_name, organization: h.organization,
        organization_name: h.organization_name, start_date: h.start_date, duration_value: h.duration_value,
        duration_unit: h.duration_unit, amount: null, status: 'completed', rating: h.rating,
      }));
      this.rows.set([...a, ...b].sort((x, y) => y.start_date.localeCompare(x.start_date)));
      this.loading.set(false);
    });
  }

  verify(r: Row) {
    this.http.post(API + `gigs/verify/${r.id}/`, {}).subscribe({
      next: () => {
        this.rows.update((l) => l.map((x) => (x.key === r.key ? { ...x, status: 'verified' } : x)));
        this.snack.open(`Verified ${r.worker_name}'s gig.`, 'OK', { duration: 3000, panelClass: 'success-snackbar' });
      },
      error: (e) => this.snack.open(e?.error?.detail || 'Could not verify.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }

  openRate(r: Row) {
    this.rating.set(r);
    this.stars.set(r.rating?.stars ?? 0);
    this.comment.set(r.rating?.comment ?? '');
    this.rateDialog?.nativeElement.showModal();
  }
  closeRate() { this.rateDialog?.nativeElement.close(); }

  saveRating() {
    const r = this.rating();
    if (!r || !this.stars()) return;
    this.saving.set(true);
    this.http.post<any>(API + `gig-history/${r.id}/rate/`, { stars: this.stars(), comment: this.comment() }).subscribe({
      next: (res) => {
        this.rows.update((l) => l.map((x) => (x.key === r.key ? { ...x, rating: { stars: res.stars, comment: res.comment } } : x)));
        this.saving.set(false);
        this.closeRate();
        this.snack.open(`Rated ${r.worker_name} ${res.stars}★. It shows on their work certificate.`, 'OK', { duration: 3500, panelClass: 'success-snackbar' });
      },
      error: (e) => { this.saving.set(false); this.snack.open(e?.error?.detail || 'Could not save the rating.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  exportCsv() {
    downloadCsv('gigs.csv', this.shown().map((r) => ({
      worker: r.worker_name, trade: r.job_type_name, site: r.organization_name, start: r.start_date,
      duration: this.duration(r.duration_value, r.duration_unit), status: r.status, pay_ksh: r.amount ?? '', rating: r.rating?.stars ?? '',
    })));
  }
}
