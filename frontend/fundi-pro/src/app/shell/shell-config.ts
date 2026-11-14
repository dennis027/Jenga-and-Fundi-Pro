import { ShellConfig } from './types';

export const SHELL_CONFIG: ShellConfig = {
  brand: 'Fundi Pro',
  brandIcon: 'construction',
  tagline: 'Worker portal',
  sections: [
    { title: 'Overview', items: [{ label: 'Dashboard', icon: 'space_dashboard', route: '/main-menu', exact: true }] },
    {
      title: 'My work',
      items: [
        { label: 'My gigs', icon: 'work', route: '/main-menu/gig-summary', badge: 'ready' },
        { label: 'Log a gig', icon: 'add_task', route: '/main-menu/gigs' },
        { label: 'Find work', icon: 'travel_explore', route: '/main-menu/search-gigs' },
      ],
    },
    {
      title: 'Reputation',
      items: [
        { label: 'Credit score', icon: 'workspace_premium', route: '/main-menu/credit-score' },
        { label: 'ID verification', icon: 'verified_user', route: '/main-menu/verification-status' },
      ],
    },
    {
      title: 'Money',
      items: [
        { label: 'Payments received', icon: 'payments', route: '/main-menu/mpesa' },
      ],
    },
    { title: 'Insights', items: [{ label: 'Analytics', icon: 'monitoring', route: '/main-menu/analytics' }] },
  ],
  quickActions: [
    { label: 'Log a gig', icon: 'add_task', route: '/main-menu/gigs' },
    { label: 'Share my work certificate', icon: 'share', route: '/main-menu/credit-score' },
    { label: 'Verify my ID', icon: 'verified_user', route: '/main-menu/verification-status' },
    { label: 'Add an M-Pesa payment', icon: 'receipt_long', route: '/main-menu/mpesa?upload=1' },
    { label: 'My profile', icon: 'person', route: '/main-menu/profile' },
  ],
};
