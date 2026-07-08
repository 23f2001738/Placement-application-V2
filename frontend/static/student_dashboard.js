const { createApp } = Vue;

createApp({
    data() {
        return {
            studentName: '',
            tab: 'drives',
            filters: { search: '', minCgpa: null, sortBy: 'created_at' },
            drives: [], applications: [], interviews: [], notifications: [],
            profile: {}, toasts: [], connectionStatus: 'Connecting...', socket: null,
            dragover: false, uploadStatus: null, debounceTimer: null,
            expanded: {}
        };
    },
    computed: {
        unreadCount() { return this.notifications.filter(n => !n.is_read).length; },
        resumeFileName() {
            if (!this.profile.resume_path) return '';
            return this.profile.resume_path.split('/').pop();
        }
    },
    mounted() { this.loadAll(); this.initSocket(); },
    methods: {
        async api(url, opts = {}) {
            const isForm = opts.body instanceof FormData;
            const headers = isForm ? {} : { 'Content-Type': 'application/json' };
            const res = await fetch(url, { credentials: 'include', headers, ...opts });
            if (res.status === 401) { window.location.href = '/'; return null; }
            const ct = res.headers.get('content-type') || '';
            if (ct.includes('application/json')) return res.json();
            return res;
        },
        async loadAll() {
            await Promise.all([
                this.loadDrives(), this.loadApplications(), this.loadInterviews(),
                this.loadNotifications(), this.loadProfile()
            ]);
        },
        debouncedLoadDrives() {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => this.loadDrives(), 300);
        },
        async loadDrives() {
            const p = new URLSearchParams();
            if (this.filters.search) p.set('search', this.filters.search);
            if (this.filters.minCgpa) p.set('min_cgpa', this.filters.minCgpa);
            if (this.filters.sortBy) p.set('sort_by', this.filters.sortBy);
            this.drives = await this.api(`/api/student/drives?${p}`) || [];
        },
        async loadApplications() { this.applications = await this.api('/api/student/applications') || []; },
        async loadInterviews() { this.interviews = await this.api('/api/student/interviews') || []; },
        async loadNotifications() { this.notifications = await this.api('/api/student/notifications') || []; },
        async loadProfile() { 
            this.profile = await this.api('/api/student/profile') || {}; 
            if (this.profile && this.profile.name) this.studentName = this.profile.name;
        },
        initSocket() {
            this.socket = io({ withCredentials: true });
            this.socket.on('connect', () => { this.connectionStatus = 'Live'; });
            this.socket.on('disconnect', () => { this.connectionStatus = 'Offline'; });
            this.socket.on('new_drive', (d) => { this.toast(`New drive: ${d.job_title} at ${d.company_name}${d.location ? ' — ' + d.location : ''}`); this.loadDrives(); });
            this.socket.on('application_updated', (d) => { this.toast(`Application updated: ${d.drive_title} → ${d.status}`); this.loadApplications(); });
            this.socket.on('interview_scheduled', () => { this.toast('New interview scheduled!'); this.loadInterviews(); this.loadApplications(); });
            this.socket.on('export_complete', (d) => this.toast(d.message));
            this.socket.on('notification', (d) => { this.toast(d.message); this.loadNotifications(); });
        },
        toast(msg) { this.toasts.unshift(msg); if (this.toasts.length > 5) this.toasts.pop(); },
        appBadge(s) {
            return { applied: 'bg-primary', shortlisted: 'bg-warning text-dark', selected: 'bg-success', rejected: 'bg-danger', interview_scheduled: 'bg-info' }[s] || 'bg-secondary';
        },
        formatDate(d) { return d ? new Date(d).toLocaleDateString('en-IN', { year:'numeric', month:'short', day:'numeric' }) : '-'; },
        async apply(id) {
            const data = await this.api(`/api/student/apply/${id}`, { method: 'POST' });
            if (data) { alert(data.message); this.loadAll(); }
        },
        async saveProfile() {
            const data = await this.api('/api/student/profile', { method: 'PUT', body: JSON.stringify(this.profile) });
            if (data) alert(data.message);
        },
        async exportCsv() {
            const data = await this.api('/api/student/export-applications', { method: 'POST' });
            if (data) alert(data.message);
        },
        handleDrop(e) {
            this.dragover = false;
            const file = e.dataTransfer.files[0];
            if (file) this.doUpload(file);
        },
        uploadResume() {
            const file = this.$refs.resumeInput.files[0];
            if (file) this.doUpload(file);
        },
        async doUpload(file) {
            const fd = new FormData();
            fd.append('resume', file);
            const res = await fetch('/api/student/resume/upload', { method: 'POST', credentials: 'include', body: fd });
            const data = await res.json();
            if (res.ok) {
                this.uploadStatus = { type: 'success', message: 'Resume uploaded successfully!' };
                this.loadProfile();
            } else {
                this.uploadStatus = { type: 'error', message: data.message || 'Upload failed' };
            }
            setTimeout(() => this.uploadStatus = null, 5000);
        },
        downloadResume() { window.open('/api/student/resume/download', '_blank'); },
        async respondInterview(id, response) {
            const data = await this.api(`/api/student/interviews/${id}/response`, {
                method: 'PUT', body: JSON.stringify({ response })
            });
            if (data) { alert(data.message); this.loadInterviews(); }
        },
        async markAsRead(id) {
            await this.api(`/api/student/notifications/${id}/read`, { method: 'PUT' });
            this.loadNotifications();
        },
        toggleDesc(id) {
            this.expanded = this.expanded || {};
            this.expanded[id] = !this.expanded[id];
        },
        async logout() {
            await this.api('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        }
    }
}).mount('#studentApp');
