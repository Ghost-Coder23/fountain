/*
 * EduCore Offline Utilities
 * Shared functions for accessing IndexedDB and rendering data offline
 */

window.EduCoreOffline = {
    // Get all data from a store
    async getAll(storeName) {
        if (!window.eduCoreDB) {
            console.error('EduCoreDB not initialized');
            return [];
        }
        return await window.eduCoreDB.getAll(storeName);
    },

    // Render student table
    renderStudents(students, containerEl) {
        if (!students || students.length === 0) {
            containerEl.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-5 text-muted">
                        <i class="bi bi-people fs-1 d-block mb-2"></i>
                        No students found.
                    </td>
                </tr>
            `;
            return;
        }

        containerEl.innerHTML = students.map(student => {
            const firstName = student.user?.first_name || '';
            const lastName = student.user?.last_name || '';
            const email = student.user?.email || '';
            const initials = (firstName[0] || '').toUpperCase() + (lastName[0] || '').toUpperCase();
            
            return `
                <tr>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div style="width:32px;height:32px;border-radius:50%;background:#e0e7ff;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:0.75rem;color:#4338ca;">
                                ${initials}
                            </div>
                            <div>
                                <div class="fw-medium">${firstName} ${lastName}</div>
                                <div class="text-muted small">${email}</div>
                            </div>
                        </div>
                    </td>
                    <td><code>${student.admission_number || ''}</code></td>
                    <td>${student.current_class || '—'}</td>
                    <td>${student.gender || ''}</td>
                    <td class="small text-muted">${student.parent_name || ''}<br>${student.parent_phone || ''}</td>
                    <td>
                        <span class="text-muted small">View/Edit (offline)</span>
                    </td>
                </tr>
            `;
        }).join('');
    },

    // Render invoice table
    renderInvoices(invoices, containerEl, role) {
        if (!invoices || invoices.length === 0) {
            containerEl.innerHTML = `
                <tr>
                    <td colspan="${role === 'secretary' ? 5 : 6}" class="text-center py-5 text-muted">
                        <i class="bi bi-receipt fs-1 d-block mb-2"></i>
                        No invoices found.
                    </td>
                </tr>
            `;
            return;
        }

        containerEl.innerHTML = invoices.map(invoice => {
            const studentName = invoice.student?.user?.get_full_name || 'Unknown Student';
            const amount = `${invoice.currency || 'USD'} ${invoice.amount || 0}`;
            const statusBadge = `<span class="badge bg-${invoice.status === 'paid' ? 'success' : invoice.status === 'partial' ? 'warning text-dark' : 'danger'}">${invoice.status || 'unpaid'}</span>`;
            
            return `
                <tr>
                    <td><span class="text-muted">${studentName}</span></td>
                    ${role !== 'secretary' ? `<td><span class="money-amount">${amount}</span></td>` : ''}
                    <td>${statusBadge}</td>
                </tr>
            `;
        }).join('');
    },

    // Search students locally
    searchStudents(students, searchTerm) {
        if (!searchTerm) return students;
        const term = searchTerm.toLowerCase().trim();
        return students.filter(student => {
            const fullName = `${student.user?.first_name || ''} ${student.user?.last_name || ''}`.toLowerCase();
            const email = (student.user?.email || '').toLowerCase();
            const admission = (student.admission_number || '').toLowerCase();
            return fullName.includes(term) || email.includes(term) || admission.includes(term);
        });
    }
};
