import { I18nService, TPipe } from '../../services/i18n';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { daysAgo } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
interface Post { id: number; title: string; description: string; county: string; constituency: string; ward: string; created_at: string; organization: number; organization_name: string; organization_phone: string | null; my_application: { id: number; status: string } | null; }

@Component({
  selector: 'app-search-gigs',
  standalone: true,
  imports: [TPipe, CommonModule, FormsModule, RouterModule],
  templateUrl: './search-gigs.html',
  styleUrl: './search-gigs.css',
})
export class SearchGigs implements OnInit {
  private i18n = inject(I18nService);
  private http = inject(HttpClient);
  private appBar = inject(AppBarService);
  private snack = inject(MatSnackBar);
  @ViewChild('applyDialog') dialog?: ElementRef<HTMLDialogElement>;
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  daysAgo = daysAgo;

  loading = signal(true);
  posts = signal<Post[]>([]);
  q = signal('');
  county = signal('');
  apps = signal<any[]>([]);
  applying = signal<Post | null>(null);
  note = signal('');
  sending = signal(false);
  accepted = computed(() => this.apps().filter((a) => a.status === 'accepted'));

  counties = computed(() => [...new Set(this.posts().map((p) => p.county))].sort());
  shown = computed(() => {
    const q = this.q().toLowerCase();
    return this.posts().filter((p) => (!this.county() || p.county === this.county())
      && (!q || `${p.title} ${p.description} ${p.organization_name} ${p.ward} ${p.constituency}`.toLowerCase().includes(q)));
  });

  ngOnInit() {
    this.appBar.setTitle('Find work');
    this.appBar.clearActions();
    if (this.browser) this.load();
  }

  load() {
    forkJoin({
      posts: this.http.get<Post[]>(API + 'gigs-available/').pipe(catchError(() => of([]))),
      apps: this.http.get<any[]>(API + 'my-applications/').pipe(catchError(() => of([]))),
    }).subscribe((r) => { this.posts.set(r.posts); this.apps.set(r.apps); this.loading.set(false); });
  }

  openApply(p: Post) { this.applying.set(p); this.note.set(''); this.dialog?.nativeElement.showModal(); }
  closeApply() { this.dialog?.nativeElement.close(); }

  apply() {
    const p = this.applying(); if (!p) return;
    this.sending.set(true);
    this.http.post<any>(API + `gigs-available/${p.id}/apply/`, { message: this.note().trim() }).subscribe({
      next: (a) => {
        this.sending.set(false); this.closeApply();
        this.posts.update((l) => l.map((x) => (x.id === p.id ? { ...x, my_application: { id: a.id, status: a.status } } : x)));
        this.apps.update((l) => [a, ...l.filter((x) => x.id !== a.id)]);
        this.snack.open(this.i18n.t('Sent to {0}. You\'ll see their answer here.', p.organization_name), this.i18n.t('OK'), { duration: 3500, panelClass: 'success-snackbar' });
      },
      error: (e) => { this.sending.set(false); this.snack.open(e?.error?.detail || this.i18n.t('Could not send.'), this.i18n.t('OK'), { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }
}
