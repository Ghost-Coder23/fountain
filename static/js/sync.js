/**
 * Sync Manager for EduCore — Fixed
 * Queues real form submissions offline and replays them later.
 *
 * FIXES:
 *  1. 403 errors: refresh CSRF token from the server before replaying the queue,
 *     because the cookie saved offline may be stale/expired by the time sync runs.
 *  2. 403 errors: on a 403 response during replay, attempt a CSRF refresh and retry once.
 *  3. SW message: listen for SW_FLUSH_QUEUE message from the service worker so
 *     flushQueue() runs even when the page was closed during offline work.
 *  4. replayQueuedForm: detect redirect-to-login (Django redirects on session expiry)
 *     and surface a clear error instead of silently succeeding.
 *  5. initialSync: called automatically on construction when online, so IndexedDB
 *     is always populated for offline use after first load.
 */

class SyncManager {
    constructor(db, tenantPrefix) {
        this.db = db;
        this.prefix = tenantPrefix;
        this.isSyncing = false;
        this.init();
    }

    init() {
        window.syncManager = this;

        // Always hide banner initially
        const banner = document.getElementById('offline-banner');
        if (banner) banner.style.display = 'none';

        window.addEventListener('online', () => this.handleOnlineStatus(true));
        window.addEventListener('offline', () => this.handleOnlineStatus(false));

        // Capture submits before the browser navigates away while offline.
        document.addEventListener('submit', (event) => this.handleFormSubmit(event), true);

        // FIX: listen for the SW_FLUSH_QUEUE message from the service worker
        // so background sync works even if the user closed and reopened the tab.
        navigator.serviceWorker?.addEventListener('message', (event) => {
            if (event.data?.type === 'SW_FLUSH_QUEUE') {
                console.log('[SyncManager] Received SW_FLUSH_QUEUE — flushing...');
                this.flushQueue();
            }
        });

        this.handleOnlineStatus(navigator.onLine);
        this.updateOfflineOpsUI().catch((error) => console.warn('Offline UI update failed:', error));

        // FIX: run initialSync on startup so data is available offline from first visit
        if (navigator.onLine) {
            this.initialSync();
        }
    }

    async updateOfflineOpsUI() {
        const sidebarBadge = document.getElementById('sync-sidebar-badge');
        const notifBadge = document.getElementById('notif-count');
        const syncPageList = document.getElementById('sync-page-list');

        const queue = await this.db.getAll('sync_queue');
        const count = queue.length;

        if (sidebarBadge) {
            if (count > 0) {
                sidebarBadge.innerText = count;
                sidebarBadge.classList.remove('d-none');
            } else {
                sidebarBadge.classList.add('d-none');
            }
        }

        if (notifBadge) {
            if (!notifBadge.hasAttribute('data-server-count')) {
                notifBadge.setAttribute('data-server-count', notifBadge.innerText || '0');
            }

            const serverCount = parseInt(notifBadge.getAttribute('data-server-count') || '0', 10) || 0;
            const total = serverCount + count;

            notifBadge.innerText = total;
            notifBadge.style.display = total > 0 ? 'flex' : 'none';
            notifBadge.title = count > 0 ? `${count} pending offline action${count === 1 ? '' : 's'}` : '';
        }

        if (syncPageList) {
            if (count === 0) {
                syncPageList.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-5">
                            <div class="text-muted">
                                <i class="bi bi-check-circle-fill text-success fs-1 d-block mb-3"></i>
                                No pending offline actions.
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }

            const rows = queue
                .slice()
                .sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0))
                .map((item) => {
                    const status = this.getQueueStatus(item);
                    const model = this.escapeHtml(this.getItemLabel(item));
                    const origin = this.escapeHtml(item.data?._offline_origin || '/');
                    const error = item.last_error
                        ? `<div class="text-danger small mt-1">${this.escapeHtml(item.last_error)}</div>`
                        : '';

                    return `
                        <tr>
                            <td>
                                <span class="badge bg-secondary text-uppercase" style="font-size: 0.65rem;">${this.escapeHtml(item.type || 'submit')}</span>
                            </td>
                            <td class="fw-semibold">${model}${error}</td>
                            <td class="text-muted small">${origin}</td>
                            <td>
                                <span class="badge ${status.className} badge-status">
                                    <i class="bi ${status.icon} me-1"></i>${status.label}
                                </span>
                            </td>
                            <td class="text-end">
                                <button class="btn btn-sm btn-outline-danger" onclick="window.syncManager.deleteFromQueue('${item.id}')">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                })
                .join('');

            syncPageList.innerHTML = rows;
        }
    }

    getQueueStatus(item) {
        if (item.last_error) {
            return {
                className: 'bg-danger-subtle text-danger',
                icon: 'bi-exclamation-triangle',
                label: 'Needs review'
            };
        }

        return {
            className: 'bg-warning text-dark',
            icon: 'bi-clock',
            label: 'Pending'
        };
    }

    getItemLabel(item) {
        const explicitLabel = item.data?._offline_label;
        if (explicitLabel) return explicitLabel;
        if (item.model) return this.prettyName(item.model);
        return 'Form Submission';
    }

    async deleteFromQueue(id) {
        if (confirm('Are you sure you want to discard this offline action?')) {
            await this.db.delete('sync_queue', id);
            await this.updateOfflineOpsUI();
        }
    }

    handleFormSubmit(event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;

        if (!navigator.onLine && this.formRequiresFileUpload(form) && !this.shouldIgnoreForm(form)) {
            event.preventDefault();
            this.showFormAlert(
                form,
                'danger',
                'This form includes file uploads, so it still needs an internet connection to submit.'
            );
            return;
        }

        if (!this.isOfflineCapableForm(form) || navigator.onLine) return;

        event.preventDefault();
        this.saveOffline(form, event.submitter || document.activeElement).catch((error) => {
            console.error('Failed to save offline:', error);
            this.showFormAlert(
                form,
                'danger',
                'We could not save this action offline. Please try again once the connection returns.'
            );
        });
    }

    shouldIgnoreForm(form) {
        return form.dataset.offlineIgnore === 'true';
    }

    isOfflineCapableForm(form) {
        const method = (form.method || 'GET').toUpperCase();
        if (method === 'GET' || this.shouldIgnoreForm(form)) return false;

        const actionUrl = this.getFormAction(form);
        if (actionUrl.origin !== window.location.origin) return false;
        if (this.isAuthRelatedPath(actionUrl.pathname)) return false;
        if (this.formRequiresFileUpload(form)) return false;

        return true;
    }

    isAuthRelatedPath(pathname) {
        return /(logout|login|password|reset)/i.test(pathname);
    }

    formRequiresFileUpload(form) {
        const enctype = (form.enctype || '').toLowerCase();
        return enctype === 'multipart/form-data' || Boolean(form.querySelector('input[type="file"]'));
    }

    getFormAction(form) {
        const action = form.getAttribute('action') || window.location.href;
        return new URL(action, window.location.origin);
    }

    determineModelName(form, submitter) {
        const explicitModel = form.getAttribute('data-offline-model');
        if (explicitModel) return explicitModel;

        const actionPath = this.getFormAction(form).pathname;
        const currentPath = window.location.pathname;
        const combinedPath = `${actionPath} ${currentPath}`.toLowerCase();
        const submitterName = (submitter?.name || '').toLowerCase();

        if (submitterName === 'add_category') return 'expense_category';
        if (submitterName === 'add_expense') return 'expense';
        if (combinedPath.includes('attendance')) return 'attendance_record';
        if (combinedPath.includes('result') || combinedPath.includes('entry') || combinedPath.includes('approval')) return 'student_result';
        if (combinedPath.includes('invoice') && combinedPath.includes('payment')) return 'fee_payment';
        if (combinedPath.includes('quick-payment')) return 'fee_payment';
        if (combinedPath.includes('invoice')) return 'fee_invoice';
        if (combinedPath.includes('structure')) return 'fee_structure';
        if (combinedPath.includes('expense')) return 'expense';
        if (combinedPath.includes('announcement')) return 'announcement';
        if (combinedPath.includes('teacher')) return 'teacher';
        if (combinedPath.includes('student')) return 'student';
        if (combinedPath.includes('subject')) return 'subject';
        if (combinedPath.includes('class') || combinedPath.includes('section')) return 'class_section';
        if (combinedPath.includes('term')) return 'term';
        if (combinedPath.includes('year')) return 'academic_year';
        if (combinedPath.includes('user') || combinedPath.includes('profile') || combinedPath.includes('settings')) return 'school_user';

        return 'form_submission';
    }

    determineOperationType(form, submitter) {
        const explicitOperation = form.getAttribute('data-offline-operation');
        if (explicitOperation) return explicitOperation;

        const actionPath = this.getFormAction(form).pathname.toLowerCase();
        const submitterText = (submitter?.innerText || submitter?.value || '').toLowerCase();

        if (actionPath.includes('delete') || submitterText.includes('delete') || submitterText.includes('remove')) {
            return 'delete';
        }
        if (actionPath.includes('add') || actionPath.includes('create') || actionPath.includes('register') || actionPath.includes('new')) {
            return 'create';
        }
        if (actionPath.includes('edit') || actionPath.includes('update') || actionPath.includes('payment') || actionPath.includes('mark')) {
            return 'update';
        }

        return 'submit';
    }

    serializeFormData(formData) {
        const entries = [];
        formData.forEach((value, key) => {
            if (value instanceof File) return;
            entries.push({ key, value: String(value) });
        });
        return entries;
    }

    async saveOffline(form, submitter) {
        try {
            console.log('[SyncManager] Saving form offline...', form);
            
            if (!this.db) {
                throw new Error('Offline database not initialized');
            }

            const formData = new FormData(form);
            if (submitter?.name && !formData.has(submitter.name)) {
                formData.append(submitter.name, submitter.value || '1');
            }

            const modelName = this.determineModelName(form, submitter);
            const opType = this.determineOperationType(form, submitter);
            const actionUrl = this.getFormAction(form);
            const itemLabel = form.getAttribute('data-offline-label') || this.prettyName(modelName);

            console.log('[SyncManager] Queue payload:', { modelName, opType, actionUrl, itemLabel });

            const queuePayload = {
                _offline_origin: `${window.location.pathname}${window.location.search}`,
                _offline_url: actionUrl.toString(),
                _offline_method: (form.method || 'POST').toUpperCase(),
                _offline_label: itemLabel,
                _offline_entries: this.serializeFormData(formData),
                _offline_saved_at: new Date().toISOString()
            };

            await this.db.queueWrite(modelName, opType, queuePayload);
            await this.updateOfflineOpsUI();

            const submitButton = submitter || form.querySelector('button[type="submit"], input[type="submit"]');
            this.decorateSubmitButton(submitButton, 'Saved Offline');
            this.showFormAlert(
                form,
                'success',
                `Saved offline. Your ${itemLabel.toLowerCase()} will sync automatically when the connection returns.`
            );
            console.log('[SyncManager] Form saved offline successfully!');
        } catch (error) {
            console.error('[SyncManager] Failed to save offline:', error);
            this.showFormAlert(
                form,
                'danger',
                `Failed to save offline: ${error.message || 'Unknown error'}. Please try again or contact support.`
            );
        }
    }

    decorateSubmitButton(button, label) {
        if (!button) return;

        if (button.tagName === 'INPUT') {
            button.value = label;
        } else {
            button.innerHTML = `<i class="bi bi-cloud-check me-1"></i>${label}`;
        }
        button.classList.remove('btn-primary', 'btn-success', 'btn-danger');
        button.classList.add('btn-warning');
        button.disabled = true;
    }

    showFormAlert(form, tone, message) {
        const existingAlert = form.querySelector('.offline-form-alert');
        if (existingAlert) existingAlert.remove();

        const alert = document.createElement('div');
        alert.className = `alert alert-${tone} offline-form-alert mt-3 shadow-sm border-0`;
        alert.innerHTML = `
            <div class="d-flex align-items-start">
                <i class="bi ${tone === 'danger' ? 'bi-exclamation-triangle-fill' : 'bi-cloud-check-fill'} fs-4 me-3"></i>
                <div>${this.escapeHtml(message)}</div>
            </div>
        `;

        form.prepend(alert);
    }

    handleOnlineStatus(isOnline) {
        console.log('[SyncManager] handleOnlineStatus called, isOnline:', isOnline);
        const banner = document.getElementById('offline-banner');
        const OFFLINE_BANNER_KEY = 'offlineBannerShown';
        
        if (!isOnline) {
            const hasShown = localStorage.getItem(OFFLINE_BANNER_KEY) === 'true';
            console.log('[SyncManager] Offline, hasShown:', hasShown);
            if (!hasShown && banner) {
                banner.style.display = 'block';
                localStorage.setItem(OFFLINE_BANNER_KEY, 'true');
                
                // Hide after 5 seconds
                setTimeout(() => {
                    if (banner) banner.style.display = 'none';
                }, 5000);
            }
            console.log('[SyncManager] App is offline. Changes will be saved locally.');
            return;
        }

        console.log('[SyncManager] Online, hiding banner and clearing flag');
        if (banner) banner.style.display = 'none';
        // Reset the flag when coming back online
        localStorage.removeItem(OFFLINE_BANNER_KEY);
        console.log('[SyncManager] App is online. Starting sync...');
        this.flushQueue();
    }

    // FIX: fetch a fresh CSRF token from the server before replaying queued forms.
    // The token saved in the cookie while offline may be expired, causing 403s.
    async refreshCsrfToken() {
        try {
            // Use dedicated CSRF refresh endpoint
            const response = await fetch('/api/csrf-refresh/', { 
                method: 'GET', 
                credentials: 'same-origin' 
            });
            if (response.ok) {
                const data = await response.json();
                if (data.csrf_token) {
                    // Update local cookie (in case browser didn't get it)
                    document.cookie = `csrftoken=${data.csrf_token}; path=/`;
                }
                console.log('[SyncManager] CSRF token refreshed successfully.');
            }
        } catch (err) {
            console.warn('[SyncManager] Could not refresh CSRF token:', err.message);
            // Fall back to hitting root page
            try {
                const fallbackResponse = await fetch('/', { method: 'GET', credentials: 'same-origin' });
                if (fallbackResponse.ok) {
                    console.log('[SyncManager] CSRF token refreshed via fallback.');
                }
            } catch (fallbackErr) {
                console.warn('[SyncManager] Fallback CSRF refresh also failed:', fallbackErr.message);
            }
        }
    }

    async flushQueue() {
        if (this.isSyncing || !navigator.onLine) return;

        const queue = await this.db.getAll('sync_queue');
        if (queue.length === 0) return;

        this.isSyncing = true;
        this.showSyncStatus('syncing');

        // FIX: always refresh the CSRF token before replaying any queued requests.
        // This is the primary cause of 403 Forbidden errors after coming back online.
        await this.refreshCsrfToken();

        let syncedCount = 0;
        let failedCount = 0;

        try {
            for (const item of queue) {
                try {
                    if (this.isReplayableFormItem(item)) {
                        await this.replayQueuedForm(item);
                    } else {
                        await this.syncLegacyQueueItem(item);
                    }
                    syncedCount += 1;
                } catch (error) {
                    failedCount += 1;
                    await this.markQueueError(item, error);
                    console.error(`[SyncManager] Sync failed for item ${item.id}:`, error);
                }
            }

            if (failedCount === 0) {
                this.showSyncStatus('synced', `${syncedCount} action${syncedCount === 1 ? '' : 's'} synced`);
            } else if (syncedCount > 0) {
                this.showSyncStatus('partial', `${syncedCount} synced, ${failedCount} still need attention`);
            } else {
                this.showSyncStatus('failed');
            }
        } finally {
            this.isSyncing = false;
            await this.updateOfflineOpsUI();
        }
    }

    isReplayableFormItem(item) {
        return Boolean(item.data?._offline_url && Array.isArray(item.data?._offline_entries));
    }

    async replayQueuedForm(item, isRetry = false) {
        const formData = new FormData();
        for (const entry of item.data._offline_entries) {
            formData.append(entry.key, entry.value);
        }

        const csrfToken = this.getCookie('csrftoken');
        const headers = {
            'X-Requested-With': 'OfflineSync',
            ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
        };

        const response = await fetch(item.data._offline_url, {
            method: (item.data._offline_method || 'POST').toUpperCase(),
            body: formData,
            headers,
            credentials: 'same-origin',
            redirect: 'follow'
        });

        // FIX: Django session expiry redirects to /login/ — detect this and surface a real error
        if (response.redirected && response.url.includes('/login')) {
            throw new Error('Session expired. Please log in again, then retry sync.');
        }

        // FIX: on 403, try refreshing the CSRF token and retry once
        if (response.status === 403 && !isRetry) {
            console.warn('[SyncManager] 403 on replay — refreshing CSRF and retrying once');
            await this.refreshCsrfToken();
            return this.replayQueuedForm(item, true);
        }

        if (!response.ok) {
            throw new Error(`Server responded with ${response.status} for ${item.data._offline_url}`);
        }

        await this.db.delete('sync_queue', item.id);
    }

    async syncLegacyQueueItem(item) {
        const response = await fetch('/api/sync/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken') || ''
            },
            body: JSON.stringify({
                operations: [{
                    model: item.model,
                    type: item.type,
                    data: item.data,
                    queue_id: item.id
                }]
            })
        });

        if (!response.ok) {
            throw new Error(`Legacy sync request failed with ${response.status}`);
        }

        const result = await response.json();
        const itemResult = result.results?.[0];
        if (!itemResult || !['success', 'conflict'].includes(itemResult.status)) {
            throw new Error(itemResult?.message || 'Legacy sync could not be completed');
        }

        await this.db.delete('sync_queue', item.id);
    }

    async markQueueError(item, error) {
        const updated = {
            ...item,
            last_error: error.message || 'Sync failed',
            last_attempt: new Date().toISOString()
        };
        await this.db.put('sync_queue', updated);
    }

    showSyncStatus(status, message = '') {
        const indicator = document.getElementById('sync-indicator');
        if (!indicator) return;

        indicator.className = 'sync-status';
        indicator.style.display = 'block';

        switch (status) {
            case 'syncing':
                indicator.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Syncing pending actions...';
                indicator.classList.add('bg-info');
                break;
            case 'synced':
                indicator.innerHTML = `<i class="bi bi-check-circle me-1"></i>${this.escapeHtml(message || 'All data synced')}`;
                indicator.classList.add('bg-success');
                setTimeout(() => { indicator.style.display = 'none'; }, 3000);
                break;
            case 'partial':
                indicator.innerHTML = `<i class="bi bi-exclamation-circle me-1"></i>${this.escapeHtml(message)}`;
                indicator.classList.add('bg-warning', 'text-dark');
                break;
            case 'failed':
                indicator.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Sync failed. <button onclick="window.syncManager.flushQueue()">Retry</button>';
                indicator.classList.add('bg-danger');
                break;
        }
    }

    prettyName(value) {
        return String(value || 'form_submission')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (char) => char.toUpperCase());
    }

    escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === `${name}=`) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async initialSync() {
        if (!navigator.onLine) return;

        try {
            const response = await fetch('/api/initial-sync/', {
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken') || ''
                }
            });
            if (response.ok) {
                const data = await response.json();

                for (const [key, value] of Object.entries(data)) {
                    if (Array.isArray(value)) {
                        await this.db.bulkPut(key, value);
                    } else if (key === 'school') {
                        await this.db.put('meta', { id: 'current_school', ...value });
                    }
                }
                console.log('[SyncManager] Initial sync completed.');
            }
        } catch (error) {
            console.error('[SyncManager] Initial sync failed:', error);
        }
    }
}

window.SyncManager = SyncManager;