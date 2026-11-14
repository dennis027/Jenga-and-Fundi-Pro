import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';

const API = environment.apiUrl + 'api/';

interface PendingGig { id: number; workerName: string; workerPhone: string; siteName: string; jobType: string; startDate: string; duration: string; location: string; }
interface Stats { total_gigs: number; unverified_gigs: number; active_workers: number; active_sites: number; verified_this_week: number; verification_rate: number; }
interface Worker { id: number; name: string; gigs: number; credit_score: number; }
interface Site { id: number; name: string; county: string; constituency: string; ward: string; is_active: boolean; }

@Component({
  selector: 'app-jenga-dash',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './jenga-dash.html',
  styleUrl: './jenga-dash.css',
})
export class JengaDash implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  site = inject(SiteContextService);

  loading = signal(true);
  name = signal('');
  stats = signal<Stats | null>(null);
  pending = signal<PendingGig[]>([]);
  workers = signal<Worker[]>([]);
  sites = signal<Site[]>([]);
  paidThisMonth = signal(0);
  verifying = signal<number | null>(null);

  today = new Date();
  greeting = (() => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'; })();

  visiblePending = computed(() => {
    const s = this.site.id() === null ? null : this.site.label();
    return this.pending().filter((g) => !s || g.siteName === s);
  });
  rate = computed(() => Math.round(this.stats()?.verification_rate ?? 0));

  ngOnInit() {
    this.appBar.setTitle('Dashboard');
    this.appBar.clearActions();
    if (this.browser) this.load();
  }

  load() {
    this.loading.set(true);
    const safe = <T>(o: any, fallback: T) => o.pipe(catchError(() => of(fallback)));
    forkJoin({
      user: safe(this.http.get<any>(API + 'user/'), null),
      stats: safe(this.http.get<Stats>(API + 'contractor/dashboard/stats/'), null),
      pending: safe(this.http.get<PendingGig[]>(API + 'contractor/dashboard/unverified-gigs/'), []),
      workers: safe(this.http.get<Worker[]>(API + 'contractor/dashboard/top-workers/'), []),
      sites: safe(this.http.get<Site[]>(API + 'user-organizations/'), []),
      payments: safe(this.http.get<any[]>(API + 'single-messages/'), []),
    }).subscribe((r: any) => {
      this.name.set((r.user?.full_name || r.user?.username || '').split(' ')[0]);
      this.stats.set(r.stats);
      this.pending.set(r.pending);
      this.workers.set(r.workers.slice(0, 5));
      this.sites.set(r.sites);
      const now = new Date();
      const tx = Array.isArray(r.payments) ? r.payments : (r.payments?.results || r.payments?.transactions || []);
      this.paidThisMonth.set(tx.filter((t: any) => {
        const d = new Date(t.transaction_date);
        return t.result_code === 0 && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
      }).reduce((s: number, t: any) => s + Number(t.amount || 0), 0));
      this.loading.set(false);
    });
  }

  verify(g: PendingGig) {
    this.verifying.set(g.id);
    this.http.post<any>(API + `gigs/verify/${g.id}/`, {}).subscribe({
      next: () => {
        this.pending.update((list) => list.filter((x) => x.id !== g.id));
        this.stats.update((s) => s && { ...s, unverified_gigs: Math.max(0, s.unverified_gigs - 1), verified_this_week: s.verified_this_week + 1 });
        this.verifying.set(null);
        this.snack.open(`Verified ${g.workerName}'s ${g.jobType.toLowerCase()} gig. +5 to their score.`, 'OK', { duration: 3500, panelClass: 'success-snackbar' });
      },
      error: (e) => {
        this.verifying.set(null);
        this.snack.open(e?.error?.detail || 'Could not verify this gig.', 'OK', { duration: 4000, panelClass: 'error-snackbar' });
      },
    });
  }

  initials(n: string) { return (n || '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase(); }
  ago(d: string) {
    const days = Math.round((Date.now() - new Date(d).getTime()) / 86400000);
    return days <= 0 ? 'today' : days === 1 ? 'yesterday' : `${days} days ago`;
  }
}
