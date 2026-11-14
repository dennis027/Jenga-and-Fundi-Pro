import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { duration } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
type Tab = 'waiting' | 'ready' | 'completed';

@Component({
  selector: 'app-gig-summary',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './gig-summary.html',
  styleUrl: './gig-summary.css',
})
export class GigSummary implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  duration = duration;
  @ViewChild('disputeDialog') disputeDialog?: ElementRef<HTMLDialogElement>;

  loading = signal(true);
  open = signal<any[]>([]);
  done = signal<any[]>([]);
  disputes = signal<any[]>([]);
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
    }).subscribe((r) => {
      this.open.set(r.open); this.done.set(r.done); this.disputes.set(r.disputes);
      if (!this.route.snapshot.queryParamMap.get('tab') && !r.open.some((g) => !g.is_verified) && r.open.some((g) => g.is_verified)) this.tab.set('ready');
      this.loading.set(false);
    });
  }

  disputeFor(kind: 'gig' | 'history', id: number) {
    return this.disputes().find((d) => d[kind] === id);
  }

  complete(g: any) {
    this.completing.set(g.id);
    this.http.post<any>(API + `gigs/${g.id}/complete/`, {}).subscribe({
      next: (res) => { this.completing.set(null); this.snack.open(`Done! Your credit score is now ${res.new_score}.`, 'OK', { duration: 3500, panelClass: 'success-snackbar' }); this.load(); },
      error: (e) => { this.completing.set(null); this.snack.open(e?.error?.error || 'Could not complete the gig.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
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
        this.snack.open('Dispute sent. Our team will review it and contact you.', 'OK', { duration: 4000, panelClass: 'success-snackbar' }); },
      error: (e) => { this.sending.set(false); this.snack.open(e?.error?.detail || 'Could not send the dispute.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
