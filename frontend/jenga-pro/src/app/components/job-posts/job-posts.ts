import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, OnInit, PLATFORM_ID, ViewChild, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, forkJoin, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';
import { daysAgo } from '../../shell/ui';

const API = environment.apiUrl + 'api/';

@Component({
  selector: 'app-job-posts',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './job-posts.html',
  styleUrl: './job-posts.css',
})
export class JobPosts implements OnInit {
  private http = inject(HttpClient);
  private snack = inject(MatSnackBar);
  private appBar = inject(AppBarService);
  private route = inject(ActivatedRoute);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  ctx = inject(SiteContextService);
  daysAgo = daysAgo;
  @ViewChild('postDialog') dialog?: ElementRef<HTMLDialogElement>;

  loading = signal(true);
  posts = signal<any[]>([]);
  sites = signal<any[]>([]);
  saving = signal(false);
  form = { organization: null as number | null, title: '', description: '' };

  shown = computed(() => this.posts().filter((p) => this.ctx.id() === null || p.organization === this.ctx.id()));

  ngOnInit() {
    this.appBar.setTitle('Job posts');
    this.appBar.clearActions();
    if (!this.browser) return;
    this.load();
    if (this.route.snapshot.queryParamMap.get('new')) setTimeout(() => this.openNew(), 300);
  }

  load() {
    forkJoin({
      posts: this.http.get<any[]>(API + 'gigs-available/', { params: { mine: 1 } }).pipe(catchError(() => of([]))),
      sites: this.http.get<any[]>(API + 'user-organizations/').pipe(catchError(() => of([]))),
    }).subscribe((r) => { this.posts.set(r.posts); this.sites.set(r.sites.filter((s) => s.is_active)); this.loading.set(false); });
  }

  openNew() {
    this.form = { organization: this.ctx.id() ?? this.sites()[0]?.id ?? null, title: '', description: '' };
    this.dialog?.nativeElement.showModal();
  }
  close() { this.dialog?.nativeElement.close(); }

  save() {
    const site = this.sites().find((s) => s.id === this.form.organization);
    if (!site || !this.form.title.trim()) return;
    this.saving.set(true);
    this.http.post<any>(API + 'gigs-available/', {
      organization: site.id, title: this.form.title.trim(), description: this.form.description.trim(),
      county: site.county, constituency: site.constituency, ward: site.ward,
    }).subscribe({
      next: (p) => { this.saving.set(false); this.close(); this.posts.update((l) => [{ ...p, organization_name: site.name }, ...l]);
        this.snack.open('Job posted. Fundis can see it under Find work.', 'OK', { duration: 3500, panelClass: 'success-snackbar' }); },
      error: () => { this.saving.set(false); this.snack.open('Could not post the job.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }); },
    });
  }

  remove(p: any) {
    if (!confirm(`Remove “${p.title}”? Fundis will no longer see it.`)) return;
    this.http.delete(API + `gigs-available/${p.id}/`).subscribe({
      next: () => { this.posts.update((l) => l.filter((x) => x.id !== p.id)); this.snack.open('Post removed.', 'OK', { duration: 2500 }); },
      error: () => this.snack.open('Could not remove the post.', 'OK', { duration: 4000, panelClass: 'error-snackbar' }),
    });
  }
}
