import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { scoreLevel } from '../fundi-dash/fundi-dash';

const API = environment.apiUrl + 'api/';
const ACTIONS: Record<string, { label: string; icon: string }> = {
  verify_gig: { label: 'Contractor verified a gig', icon: 'fact_check' },
  complete_gig: { label: 'Gig completed', icon: 'task_alt' },
  approve_verification: { label: 'ID verified', icon: 'verified_user' },
  adjustment: { label: 'Adjustment by support', icon: 'tune' },
};

@Component({
  selector: 'app-credit-score',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './credit-score.html',
  styleUrl: './credit-score.css',
})
export class CreditScore implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  actions = ACTIONS;

  loading = signal(true);
  me = signal<any>(null);
  history = signal<any[]>([]);
  certUrl = signal<string | null>(null);
  certBusy = signal(false);
  copied = signal(false);

  score = computed(() => this.me()?.credit_score ?? 0);
  level = computed(() => scoreLevel(this.score()));
  thisMonth = computed(() => {
    const now = new Date();
    return this.history().filter((h) => { const d = new Date(h.timestamp); return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear(); })
      .reduce((s, h) => s + h.change, 0);
  });
  tone = computed(() => (this.score() >= 60 ? 'ok' : this.score() >= 30 ? 'warn' : 'danger'));

  ngOnInit() {
    this.appBar.setTitle('Credit score');
    this.appBar.clearActions();
    if (!this.browser) return;
    forkJoin({
      me: this.http.get<any>(API + 'user/').pipe(catchError(() => of(null))),
      history: this.http.get<any[]>(API + 'credit-history/').pipe(catchError(() => of([]))),
    }).subscribe((r) => {
      this.me.set(r.me);
      this.history.set([...r.history].sort((a, b) => b.timestamp.localeCompare(a.timestamp)));
      this.loading.set(false);
    });
  }

  share() {
    this.certBusy.set(true);
    this.http.get<any>(API + 'certificate/link/').subscribe({
      next: async (res) => {
        this.certUrl.set(res.url); this.certBusy.set(false);
        const nav = navigator as Navigator & { share?: (d: ShareData) => Promise<void> };
        try {
          if (nav.share) { await nav.share({ title: 'My verified work certificate', url: res.url }); return; }
          await navigator.clipboard.writeText(res.url); this.copied.set(true);
        } catch { /* user cancelled share or clipboard blocked: link stays visible */ }
      },
      error: () => { this.certBusy.set(false); this.snack.open('Could not create the link. Please try again.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
