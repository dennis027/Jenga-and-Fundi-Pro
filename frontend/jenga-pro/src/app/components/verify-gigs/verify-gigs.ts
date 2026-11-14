import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnDestroy, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';
import { daysAgo, duration, initials } from '../../shell/ui';

const API = environment.apiUrl + 'api/';

interface Gig {
  id: number; worker_name: string; job_type_name: string; organization: number; organization_name: string;
  start_date: string; duration_value: number; duration_unit: string; amount_paid: string; is_verified: boolean;
  county: string; constituency: string; ward: string; created_at: string;
}

@Component({
  selector: 'app-verify-gigs',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './verify-gigs.html',
  styleUrl: './verify-gigs.css',
})
export class VerifyGigs implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  site = inject(SiteContextService);
  initials = initials; daysAgo = daysAgo; duration = duration;

  loading = signal(true);
  gigs = signal<Gig[]>([]);
  q = signal('');
  selected = signal<Set<number>>(new Set());
  busy = signal(false);
  rejecting = signal<Gig | null>(null);
  reason = signal('');
  @ViewChild('rejectDialog') rejectRef?: ElementRef<HTMLDialogElement>;

  pending = computed(() => {
    const q = this.q().toLowerCase();
    return this.gigs()
      .filter((g) => !g.is_verified)
      .filter((g) => this.site.id() === null || g.organization === this.site.id())
      .filter((g) => !q || `${g.worker_name} ${g.job_type_name} ${g.organization_name} ${g.ward}`.toLowerCase().includes(q))
      .sort((a, b) => a.start_date.localeCompare(b.start_date));
  });
  allSelected = computed(() => this.pending().length > 0 && this.pending().every((g) => this.selected().has(g.id)));
  workersWaiting = computed(() => new Set(this.pending().map((g) => g.worker_name)).size);
  pendingValue = computed(() => this.pending().reduce((s, g) => s + Number(g.amount_paid || 0), 0));

  ngOnInit() {
    this.appBar.setTitle('Verify gigs');
    this.appBar.setActions([{ id: 'refresh', icon: 'refresh', ariaLabel: 'Refresh', onClick: () => this.load() }]);
    if (this.browser) this.load();
  }
  ngOnDestroy() { this.appBar.clearActions(); }

  load() {
    this.loading.set(true);
    this.http.get<Gig[]>(API + 'org-gigs-list/').subscribe({
      next: (g) => { this.gigs.set(g); this.selected.set(new Set()); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  toggle(id: number) {
    const s = new Set(this.selected());
    s.has(id) ? s.delete(id) : s.add(id);
    this.selected.set(s);
  }
  toggleAll() {
    this.selected.set(this.allSelected() ? new Set() : new Set(this.pending().map((g) => g.id)));
  }

  verifySelected() { this.verify(Array.from(this.selected())); }

  verify(ids: number[]) {
    if (!ids.length) return;
    this.busy.set(true);
    this.http.post<{ verified: number; results: { id: number; ok: boolean; detail: string }[] }>(API + 'gigs/verify-bulk/', { ids }).subscribe({
      next: (r) => {
        const ok = new Set(r.results.filter((x) => x.ok).map((x) => x.id));
        this.gigs.update((list) => list.map((g) => (ok.has(g.id) ? { ...g, is_verified: true } : g)));
        const failed = ids.length - ok.size;
        this.busy.set(false);
        this.selected.set(new Set());
        this.snack.open(failed ? `${ok.size} verified, ${failed} failed: ${r.results.find((x) => !x.ok)?.detail}` : `${ok.size} gig${ok.size > 1 ? 's' : ''} verified. Workers earned +5 each.`,
          'OK', { duration: 4000, panelClass: failed ? 'error-snackbar' : 'success-snackbar' });
      },
      error: (e) => { this.busy.set(false); this.snack.open(e?.error?.detail || 'Could not verify.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  openReject(g: Gig) { this.rejecting.set(g); this.reason.set(''); this.rejectRef?.nativeElement.showModal(); }

  reject(dlg: HTMLDialogElement) {
    const g = this.rejecting(); if (!g) return;
    this.busy.set(true);
    this.http.post(API + `gigs/${g.id}/reject/`, { reason: this.reason().trim() }).subscribe({
      next: () => {
        this.busy.set(false); dlg.close();
        this.gigs.update((l) => l.filter((x) => x.id !== g.id));
        this.snack.open(`Rejected. ${g.worker_name} was told why.`, 'OK', { duration: 3500, panelClass: 'success-snackbar' });
      },
      error: (e) => { this.busy.set(false); this.snack.open(e?.error?.detail || 'Could not reject.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
