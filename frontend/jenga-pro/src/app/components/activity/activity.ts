import { CommonModule, isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { environment } from '../../../environments/environment';
import { AppBarService } from '../../services/app-bar-service';
import { SiteContextService } from '../../shell/site-context';

const API = environment.apiUrl + 'api/';
const ICONS: Record<string, string> = {
  gig_verified: 'task_alt', gig_rejected: 'block', gig_completed: 'done_all', hired: 'handshake', invited: 'send',
  job_posted: 'campaign', job_closed: 'pause_circle', job_reopened: 'play_circle', incident_reported: 'health_and_safety',
  incident_resolved: 'check_circle', budget_set: 'savings',
};

@Component({
  selector: 'app-activity',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
<div class="page">
  <div class="page-head"><div><h1>Activity</h1><p>A record of what happened at your sites: verifications, rejections, hires, posts and safety reports.</p></div></div>
  <div class="panel">
    <div class="toolbar">
      <div class="muted">{{ ctx.id() === null ? 'All your sites' : ctx.label() }} · latest 100</div>
      <label class="search"><input type="search" placeholder="Filter" [ngModel]="q()" (ngModelChange)="q.set($event)"><span class="icon">filter_list</span></label>
    </div>
    @if (loading()) {
      <div class="panel-body"><div class="skeleton" style="height:200px"></div></div>
    } @else {
      <ol class="timeline">
        @for (g of grouped(); track g.day) {
          <li class="day">{{ g.day | date: 'EEEE d MMMM y' }}</li>
          @for (a of g.items; track a.id) {
            <li class="event">
              <span class="ev-icon" [ngClass]="a.action"><span class="icon">{{ icon(a.action) }}</span></span>
              <div class="grow"><div>{{ a.summary }}</div>
                <small class="muted">{{ a.created_at | date: 'HH:mm' }}@if (a.site) { · {{ a.site }} }@if (a.actor) { · {{ a.actor }} }</small></div>
            </li>
          }
        } @empty {
          <li><div class="empty"><span class="icon">history</span><h3>No activity yet</h3><p>Actions at your sites will be recorded here.</p></div></li>
        }
      </ol>
    }
  </div>
</div>`,
  styles: [`
    .timeline { list-style: none; margin: 0; padding: 8px 22px 22px; }
    .day { font-size: .76rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--faint); padding: 16px 0 6px; }
    .event { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid var(--border); }
    .event .grow { flex: 1; min-width: 0; }
    .ev-icon { width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center; flex: none; background: var(--primary-soft); color: var(--primary); }
    .ev-icon .icon { font-size: 18px; }
    .ev-icon.gig_rejected, .ev-icon.incident_reported { background: var(--danger-soft); color: var(--danger); }
    .ev-icon.gig_verified, .ev-icon.hired, .ev-icon.gig_completed, .ev-icon.incident_resolved { background: var(--success-soft); color: var(--success); }
  `],
})
export class Activity implements OnInit {
  private http = inject(HttpClient);
  private appBar = inject(AppBarService);
  private browser = isPlatformBrowser(inject(PLATFORM_ID));
  ctx = inject(SiteContextService);
  loading = signal(true);
  items = signal<any[]>([]);
  q = signal('');

  grouped = computed(() => {
    const q = this.q().toLowerCase();
    const list = this.items().filter((a) => (this.ctx.id() === null || a.site === this.ctx.label())
      && (!q || `${a.summary} ${a.site} ${a.actor}`.toLowerCase().includes(q)));
    const out: { day: string; items: any[] }[] = [];
    list.forEach((a) => {
      const day = a.created_at.slice(0, 10);
      const last = out[out.length - 1];
      if (last && last.day === day) last.items.push(a); else out.push({ day, items: [a] });
    });
    return out;
  });

  ngOnInit() {
    this.appBar.setTitle('Activity');
    this.appBar.clearActions();
    if (this.browser) this.http.get<any[]>(API + 'activity/').subscribe({
      next: (a) => { this.items.set(a); this.loading.set(false); }, error: () => this.loading.set(false),
    });
  }

  icon(a: string) { return ICONS[a] || 'history'; }
}
