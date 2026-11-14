import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';

const API = environment.apiUrl + 'api/';
interface Site { id: number; name: string; county: string; constituency: string; ward: string; is_active: boolean; }
interface Trade { id: number; name: string; }

@Component({
  selector: 'app-add-gig',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './add-gig.html',
  styleUrl: './add-gig.css',
})
export class AddGig implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));

  sites = signal<Site[]>([]);
  siteQ = signal('');
  site = signal<Site | null>(null);
  trades = signal<Trade[]>([]);
  tradesLoading = signal(false);
  saving = signal(false);
  today = new Date().toISOString().slice(0, 10);
  form = { job_type: null as number | null, start_date: this.today, duration_value: 1, duration_unit: 'days', amount_paid: '' as string | number };

  matches = computed(() => {
    const q = this.siteQ().toLowerCase();
    return this.sites().filter((s) => s.is_active && (!q || `${s.name} ${s.ward} ${s.constituency} ${s.county}`.toLowerCase().includes(q))).slice(0, 8);
  });

  ngOnInit() {
    this.appBar.setTitle('Log a gig');
    this.appBar.clearActions();
    if (this.browser) this.http.get<Site[]>(API + 'organizations/').subscribe((s) => {
      this.sites.set(s);
      const pre = Number(this.route.snapshot.queryParamMap.get('site'));
      const hit = pre ? s.find((x) => x.id === pre && x.is_active) : null;
      if (hit) this.pickSite(hit);
    });
  }

  pickSite(s: Site) {
    this.site.set(s);
    this.form.job_type = null;
    this.tradesLoading.set(true);
    this.http.get<Trade[]>(API + 'job-types/', { params: { organization: s.id } }).subscribe({
      next: (t) => { this.trades.set([...t].sort((a, b) => a.name.localeCompare(b.name))); this.tradesLoading.set(false); },
      error: () => this.tradesLoading.set(false),
    });
  }
  clearSite() { this.site.set(null); this.trades.set([]); this.form.job_type = null; }

  valid() { return !!this.site() && !!this.form.job_type && !!this.form.start_date && this.form.duration_value >= 1 && this.form.start_date <= this.today; }

  submit() {
    if (!this.valid()) return;
    this.saving.set(true);
    const payload = { ...this.form, organization: this.site()!.id, amount_paid: this.form.amount_paid === '' ? 0 : this.form.amount_paid };
    this.http.post<any>(API + 'gigs/', payload).subscribe({
      next: () => {
        this.saving.set(false);
        this.snack.open(`Logged. ${this.site()!.name}'s contractor will verify it.`, 'OK', { duration: 4000, panelClass: 'success-snackbar' });
        this.router.navigate(['/main-menu/gig-summary'], { queryParams: { tab: 'waiting' } });
      },
      error: (e) => {
        this.saving.set(false);
        const msg = e?.error?.detail || Object.values(e?.error || {}).flat().join(' ') || 'Could not log the gig.';
        this.snack.open(String(msg), 'OK', { duration: 5000, panelClass: 'error-snackbar' });
      },
    });
  }
}
