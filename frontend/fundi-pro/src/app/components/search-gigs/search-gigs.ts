import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { daysAgo } from '../../shell/ui';

const API = environment.apiUrl + 'api/';
interface Post { id: number; title: string; description: string; county: string; constituency: string; ward: string; created_at: string; organization: number; organization_name: string; organization_phone: string | null; }

@Component({
  selector: 'app-search-gigs',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './search-gigs.html',
  styleUrl: './search-gigs.css',
})
export class SearchGigs implements OnInit {
  private http = inject(HttpClient);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  daysAgo = daysAgo;

  loading = signal(true);
  posts = signal<Post[]>([]);
  q = signal('');
  county = signal('');

  counties = computed(() => [...new Set(this.posts().map((p) => p.county))].sort());
  shown = computed(() => {
    const q = this.q().toLowerCase();
    return this.posts().filter((p) => (!this.county() || p.county === this.county())
      && (!q || `${p.title} ${p.description} ${p.organization_name} ${p.ward} ${p.constituency}`.toLowerCase().includes(q)));
  });

  ngOnInit() {
    this.appBar.setTitle('Find work');
    this.appBar.clearActions();
    if (this.browser) this.http.get<Post[]>(API + 'gigs-available/').subscribe({
      next: (p) => { this.posts.set(p); this.loading.set(false); }, error: () => this.loading.set(false),
    });
  }
}
