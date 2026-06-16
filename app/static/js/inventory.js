/**
 * Inventory Module JavaScript
 * Extracted from inventory.html inline <script>
 *
 * Expects window.__INV_DATA to be set before this script loads:
 *   - ingredientChoices: array of {id, name, unit, cost}
 *   - activeTab: string
 *   - lastSuppliers: object mapping ingredient_id -> supplier_id
 *   - spendBySupplier: array of {name, total_spend_cents}
 */

document.addEventListener('DOMContentLoaded', () => {
    const ingredientChoices = window.__INV_DATA.ingredientChoices || [];
    const activeTabFromUrl = window.__INV_DATA.activeTab || 'stock';
    const lastSuppliers = window.__INV_DATA.lastSuppliers || {};
    const spendData = window.__INV_DATA.spendBySupplier || [];

    // ─── Tab Preservation ───
    if (activeTabFromUrl && activeTabFromUrl !== 'stock') {
        const tabEl = document.querySelector(`#inventoryTabs button[data-bs-target="#${activeTabFromUrl}-pane"]`);
        if (tabEl) {
            bootstrap.Tab.getInstance(tabEl)?.show() || new bootstrap.Tab(tabEl).show();
        }
    }

    // ─── Stock Search ───
    const searchInput = document.getElementById('inventorySearch');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('tbody.inventory-table-body tr');
            rows.forEach(row => {
                const name = row.querySelector('span').textContent.toLowerCase();
                if (name.includes(term)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // ─── Edit Ingredient Modal ───
    const editIngredientModal = document.getElementById('editIngredientModal');
    if (editIngredientModal) {
        editIngredientModal.addEventListener('show.bs.modal', (event) => {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const name = button.getAttribute('data-name');
            const unit = button.getAttribute('data-unit');
            const reorder = button.getAttribute('data-reorder');
            const supplier = button.getAttribute('data-supplier');
            const active = button.getAttribute('data-active');
            const image = button.getAttribute('data-image') || '';

            const form = editIngredientModal.querySelector('#editIngredientForm');
            form.action = `/inventory/ingredients/${id}/edit`;

            editIngredientModal.querySelector('#editName').value = name;
            editIngredientModal.querySelector('#editUnit').value = unit;
            editIngredientModal.querySelector('#editReorderLevel').value = reorder;
            editIngredientModal.querySelector('#editDefaultSupplier').value = supplier;
            editIngredientModal.querySelector('#editIsActive').value = active;
            editIngredientModal.querySelector('#editImagePath').value = image;
        });
    }

    // ─── Add Stock Modal ───
    const addStockModal = document.getElementById('addStockModal');
    if (addStockModal) {
        const select = document.getElementById('batchIngredientId');
        const qtyInput = document.getElementById('batchQtyReceived');
        const costInput = document.getElementById('batchCostPerUnit');
        const totalCostDisplay = document.getElementById('batchTotalCost');
        const batchUnitDisplay = document.getElementById('batchUnit');

        function updateBatchTotal() {
            if (qtyInput && costInput && totalCostDisplay) {
                const qty = parseFloat(qtyInput.value) || 0;
                const cost = parseFloat(costInput.value) || 0;
                totalCostDisplay.textContent = (qty * cost).toFixed(2);
            }
        }

        function handleIngredientChange() {
            if (select) {
                const selectedId = parseInt(select.value);
                const ingredient = ingredientChoices.find(i => i.id === selectedId);
                if (ingredient) {
                    if (batchUnitDisplay) {
                        batchUnitDisplay.textContent = ingredient.unit;
                    }
                    if (costInput) {
                        costInput.value = ingredient.cost.toFixed(2);
                    }
                }
                updateBatchTotal();
            }
        }

        if (select) {
            select.addEventListener('change', handleIngredientChange);
        }

        addStockModal.addEventListener('show.bs.modal', (event) => {
            const button = event.relatedTarget;
            if (button && button.classList.contains('add-stock-btn')) {
                const id = button.getAttribute('data-id');
                if (select) {
                    select.value = id;
                }
            }
            // Trigger change handler to populate default cost and unit label on modal open
            handleIngredientChange();
        });

        if (qtyInput) qtyInput.addEventListener('input', updateBatchTotal);
        if (costInput) costInput.addEventListener('input', updateBatchTotal);
    }

    // ─── Remove Stock Modal ───
    const removeStockModal = document.getElementById('removeStockModal');
    if (removeStockModal) {
        removeStockModal.addEventListener('show.bs.modal', (event) => {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const name = button.getAttribute('data-name');
            const unit = button.getAttribute('data-unit');

            removeStockModal.querySelector('#removeIngredientId').value = id;
            removeStockModal.querySelector('#removeIngredientName').value = name;
            removeStockModal.querySelector('#removeUnit').textContent = unit;
        });
    }

    // ─── Update Stock Modal ───
    const updateStockModal = document.getElementById('updateStockModal');
    if (updateStockModal) {
        updateStockModal.addEventListener('show.bs.modal', (event) => {
            const button = event.relatedTarget;
            if (button) {
                const id = button.getAttribute('data-id');
                const name = button.getAttribute('data-name');
                const qty = button.getAttribute('data-qty');
                const unit = button.getAttribute('data-unit');

                updateStockModal.querySelector('#adjustIngredientId').value = id;
                updateStockModal.querySelector('#adjustIngredientName').value = name;
                updateStockModal.querySelector('#adjustCurrentQty').value = qty;
                updateStockModal.querySelector('#adjustUnitCurrent').textContent = unit;
                updateStockModal.querySelector('#adjustUnitNew').textContent = unit;
            }
        });
    }

    // ─── Ingredient History Modal (AJAX) ───
    const historyModal = document.getElementById('historyModal');
    if (historyModal) {
        historyModal.addEventListener('show.bs.modal', async (event) => {
            const button = event.relatedTarget;
            const id = button.getAttribute('data-id');
            const name = button.getAttribute('data-name');

            document.getElementById('historyIngredientName').textContent = name;

            const tbody = document.getElementById('historyTbody');
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary"><i class="fa-solid fa-spinner fa-spin me-1"></i> Loading history...</td></tr>';

            try {
                const response = await fetch(`/inventory/ingredients/${id}/history`);
                if (response.ok) {
                    const json = await response.json();
                    tbody.innerHTML = '';
                    if (json.data && json.data.length > 0) {
                        json.data.forEach(item => {
                            let changeClass = 'text-light';
                            if (item.qty_change.startsWith('+')) {
                                changeClass = 'text-success fw-bold';
                            } else if (item.qty_change.startsWith('-')) {
                                changeClass = 'text-danger fw-bold';
                            }
                            tbody.innerHTML += `
                                <tr>
                                    <td>${item.date}</td>
                                    <td><span class="badge bg-dark border border-secondary text-light">${item.action}</span></td>
                                    <td class="${changeClass}">${item.qty_change}</td>
                                    <td class="small text-secondary">${item.reason}</td>
                                    <td><span class="text-emerald small"><i class="fa-solid fa-user me-1"></i>${item.user}</span></td>
                                </tr>
                            `;
                        });
                    } else {
                        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary">No stock change history found for this ingredient.</td></tr>';
                    }
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Failed to load history.</td></tr>';
                }
            } catch (err) {
                console.error(err);
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Error loading history data.</td></tr>';
            }
        });
    }

    // ─── Dynamic PO Row Handling ───
    let itemIndex = 0;
    const addPORowBtn = document.getElementById('addPORowBtn');
    const poItemsTbody = document.getElementById('poItemsTbody');

    function updatePOTotal() {
        let total = 0;
        const rows = poItemsTbody.querySelectorAll('tr');
        rows.forEach(row => {
            const qty = parseFloat(row.querySelector('.po-qty-input').value || 0);
            const cost = parseFloat(row.querySelector('.po-cost-input').value || 0);
            total += qty * cost;
        });
        document.getElementById('poEstimatedTotal').textContent = `$${total.toFixed(2)}`;
    }

    function addPORow() {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <select class="form-select form-dark po-ing-select" name="items-${itemIndex}-ingredient_id" required>
                    <option value="" disabled selected>Select ingredient</option>
                    ${ingredientChoices.map(i => `<option value="${i.id}" data-cost="${i.cost}" data-unit="${i.unit}">${i.name} (${i.unit})</option>`).join('')}
                </select>
            </td>
            <td>
                <div class="input-group input-group-sm">
                    <input type="number" step="0.001" min="0.001" class="form-control form-dark po-qty-input" name="items-${itemIndex}-ordered_qty" required placeholder="0.000">
                    <span class="input-group-text bg-dark border-secondary text-secondary po-unit-lbl">unit</span>
                </div>
            </td>
            <td>
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-dark border-secondary text-secondary">$</span>
                    <input type="number" step="0.01" min="0.00" class="form-control form-dark po-cost-input" name="items-${itemIndex}-unit_cost" required placeholder="0.00">
                </div>
            </td>
            <td>
                <button type="button" class="btn btn-sm btn-outline-danger remove-po-row-btn"><i class="fa-solid fa-trash"></i></button>
            </td>
        `;

        // Row listeners
        tr.querySelector('.po-ing-select').addEventListener('change', (e) => {
            const opt = e.target.selectedOptions[0];
            const unit = opt.getAttribute('data-unit');
            const defaultCost = opt.getAttribute('data-cost');
            tr.querySelector('.po-unit-lbl').textContent = unit;
            tr.querySelector('.po-cost-input').value = defaultCost;
            updatePOTotal();
        });

        tr.querySelector('.po-qty-input').addEventListener('input', updatePOTotal);
        tr.querySelector('.po-cost-input').addEventListener('input', updatePOTotal);
        tr.querySelector('.remove-po-row-btn').addEventListener('click', () => {
            tr.remove();
            updatePOTotal();
        });

        poItemsTbody.appendChild(tr);
        itemIndex++;
    }

    if (addPORowBtn) {
        addPORowBtn.addEventListener('click', addPORow);
        // Add initial row
        addPORow();
    }

    // ─── Low Stock → Create Supplier Order Shortcut ───
    const createPoShortcutBtns = document.querySelectorAll('.create-po-shortcut-btn');
    createPoShortcutBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const ingredientId = parseInt(btn.getAttribute('data-id'));
            const lastSupplierId = lastSuppliers[ingredientId] || '';

            // Switch tab to Purchasing
            const purchasingTabEl = document.querySelector('#purchasing-tab');
            if (purchasingTabEl) {
                bootstrap.Tab.getInstance(purchasingTabEl)?.show() || new bootstrap.Tab(purchasingTabEl).show();
            }

            // Open Create Supplier Order Modal
            const poModalEl = document.getElementById('createOrderModal');
            if (poModalEl) {
                const poModal = bootstrap.Modal.getInstance(poModalEl) || new bootstrap.Modal(poModalEl);
                poModal.show();

                // Pre-fill supplier if known
                const poSupplierSelect = document.getElementById('poSupplier');
                if (poSupplierSelect) {
                    poSupplierSelect.value = lastSupplierId;
                }

                // Clear dynamic rows and add just one prefilled
                poItemsTbody.innerHTML = '';
                addPORow();

                const lastRow = poItemsTbody.lastElementChild;
                if (lastRow) {
                    const selectEl = lastRow.querySelector('.po-ing-select');
                    if (selectEl) {
                        selectEl.value = ingredientId;
                        selectEl.dispatchEvent(new Event('change'));
                    }
                }
            }
        });
    });

    // ─── Supplier Order Detail View (AJAX) ───
    const viewPOBtns = document.querySelectorAll('.view-po-btn');
    const orderDetailModal = new bootstrap.Modal(document.getElementById('orderDetailModal'));
    viewPOBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.getAttribute('data-id');
            const response = await fetch(`/inventory/purchase-orders/${id}`);
            if (response.ok) {
                const data = await response.json();

                document.getElementById('detPONumber').textContent = data.po_number;
                document.getElementById('detPOSupplier').textContent = data.supplier_name;
                document.getElementById('detPOInvoiceRef').textContent = data.invoice_ref || 'N/A';

                document.getElementById('detPOCreatedBy').textContent = data.created_by_name || 'N/A';
                document.getElementById('detPOApprovedBy').textContent = data.approved_by_name || 'N/A';
                document.getElementById('detPOReceivedBy').textContent = data.received_by_name || 'N/A';

                document.getElementById('detPOCreatedAt').textContent = data.created_at || 'N/A';
                document.getElementById('detPOApprovedAt').textContent = data.approved_at || 'N/A';
                document.getElementById('detPOOrderedAt').textContent = data.ordered_at || 'N/A';
                document.getElementById('detPOExpectedAt').textContent = data.expected_at || 'N/A';
                document.getElementById('detPOReceivedAt').textContent = data.received_at || 'N/A';
                document.getElementById('detPONotes').textContent = data.notes || 'No notes left.';

                // Status Badge
                const statusSpan = document.getElementById('detPOStatus');
                statusSpan.className = 'badge';
                if (data.status === 'draft') statusSpan.className += ' bg-secondary';
                else if (data.status === 'received') statusSpan.className += ' bg-success';
                else if (data.status === 'partially_received') statusSpan.className += ' bg-warning text-dark';
                else statusSpan.className += ' bg-primary';
                statusSpan.textContent = data.status.toUpperCase();

                // Items table
                const tbody = document.getElementById('detPOTbody');
                tbody.innerHTML = '';
                let poTotal = 0;
                data.items.forEach(item => {
                    const rowTotal = item.ordered_qty * item.unit_cost;
                    poTotal += rowTotal;
                    tbody.innerHTML += `
                        <tr>
                            <td class="fw-semibold text-light">${item.ingredient_name}</td>
                            <td class="text-secondary">${item.unit}</td>
                            <td>${item.ordered_qty}</td>
                            <td>${item.received_qty}</td>
                            <td>$${item.unit_cost.toFixed(2)}</td>
                            <td class="text-emerald fw-bold">$${rowTotal.toFixed(2)}</td>
                        </tr>
                    `;
                });
                document.getElementById('detPOTotal').textContent = `$${poTotal.toFixed(2)}`;
                orderDetailModal.show();
            }
        });
    });

    // ─── Receive Delivery Modal (AJAX) ───
    const receivePOBtns = document.querySelectorAll('.receive-po-btn');
    const receiveDeliveryModal = new bootstrap.Modal(document.getElementById('receiveDeliveryModal'));
    receivePOBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.getAttribute('data-id');
            const response = await fetch(`/inventory/purchase-orders/${id}`);
            if (response.ok) {
                const data = await response.json();

                document.getElementById('receivePOForm').action = `/inventory/purchase-orders/${id}/receive`;

                const tbody = document.getElementById('recPOTbody');
                tbody.innerHTML = '';

                data.items.forEach(item => {
                    const remaining = item.ordered_qty - item.received_qty;
                    tbody.innerHTML += `
                        <tr>
                            <td class="fw-semibold text-light">${item.ingredient_name}</td>
                            <td>${item.received_qty} / ${item.ordered_qty} <span class="text-secondary small">${item.unit}</span></td>
                            <td>
                                <div class="input-group input-group-sm">
                                    <input type="number" step="0.001" min="0" max="${remaining}" class="form-control form-dark" name="received_qty_${item.purchase_order_item_id}" value="${remaining}" required>
                                    <span class="input-group-text bg-dark border-secondary text-secondary">${item.unit}</span>
                                </div>
                            </td>
                            <td>
                                <div class="input-group input-group-sm">
                                    <span class="input-group-text bg-dark border-secondary text-secondary">$</span>
                                    <input type="number" step="0.01" min="0" class="form-control form-dark rec-cost-input" name="actual_unit_cost_${item.purchase_order_item_id}" value="${item.unit_cost.toFixed(2)}" data-expected-cost="${item.unit_cost}" required>
                                </div>
                                <span class="price-variance-warning text-xs mt-1 d-block text-warning" style="display: none; font-size: 0.75rem;"></span>
                            </td>
                            <td>
                                <input type="date" class="form-control form-dark form-control-sm" name="expiry_date_${item.purchase_order_item_id}">
                            </td>
                            <td>
                                <input type="text" class="form-control form-dark form-control-sm" name="supplier_ref_${item.purchase_order_item_id}" placeholder="Batch Ref">
                            </td>
                            <td>
                                <input type="text" class="form-control form-dark form-control-sm" name="notes_${item.purchase_order_item_id}" placeholder="Lot notes...">
                            </td>
                        </tr>
                    `;
                });

                // Price variance alert listeners
                tbody.querySelectorAll('.rec-cost-input').forEach(input => {
                    const checkVariance = () => {
                        const actual = parseFloat(input.value || 0);
                        const expected = parseFloat(input.getAttribute('data-expected-cost') || 0);
                        const warningSpan = input.closest('td').querySelector('.price-variance-warning');
                        if (expected > 0 && warningSpan) {
                            const diff = actual - expected;
                            const variancePct = (diff / expected) * 100;
                            if (Math.abs(variancePct) >= 10.0) {
                                warningSpan.style.display = 'block';
                                warningSpan.innerHTML = `⚠️ Cost changed: ${variancePct > 0 ? '+' : ''}${variancePct.toFixed(1)}%`;
                            } else {
                                warningSpan.style.display = 'none';
                            }
                        }
                    };
                    input.addEventListener('input', checkVariance);
                    checkVariance();
                });

                receiveDeliveryModal.show();
            }
        });
    });

    // ─── Cancel PO Confirmation ───
    const cancelPOBtns = document.querySelectorAll('.cancel-po-btn');
    const cancelOrderModal = new bootstrap.Modal(document.getElementById('cancelOrderModal'));
    cancelPOBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.getAttribute('data-id');
            document.getElementById('cancelOrderForm').action = `/inventory/purchase-orders/${id}/cancel`;
            cancelOrderModal.show();
        });
    });

    // ─── Chart.js Supplier Spend ───
    const ctx = document.getElementById('supplierSpendChart');
    if (ctx) {
        const labels = spendData.map(r => r.name);
        const data = spendData.map(r => r.total_spend_cents / 100.0);

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Spend by Supplier ($)',
                    data: data,
                    backgroundColor: 'rgba(16, 185, 129, 0.6)',
                    borderColor: 'rgb(16, 185, 129)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8'
                        }
                    }
                }
            }
        });
    }

    // ─── Supplier Directory: Search, Filter, Sort ───
    const supplierSearch = document.getElementById('supplierSearchInput');
    const supplierFilter = document.getElementById('supplierFilterSelect');
    const supplierSort = document.getElementById('supplierSortSelect');
    const supplierCards = document.querySelectorAll('.supplier-card-col');
    const supplierNoResults = document.getElementById('supplierNoResults');
    const supplierCountBadge = document.getElementById('supplierCountBadge');

    function applySupplierFilters() {
        if (!supplierCards.length) return;

        const query = (supplierSearch?.value || '').toLowerCase();
        const filter = supplierFilter?.value || 'all';
        let visibleCards = [];

        supplierCards.forEach(card => {
            const name = card.dataset.name || '';
            const contact = card.dataset.contact || '';
            const isActive = card.dataset.active;
            const isPreferred = card.dataset.preferred;
            const overdue = parseInt(card.dataset.overdue || 0);

            const matchesSearch = !query || name.includes(query) || contact.includes(query);

            let matchesFilter = true;
            if (filter === 'active') matchesFilter = isActive === '1';
            else if (filter === 'inactive') matchesFilter = isActive !== '1';
            else if (filter === 'preferred') matchesFilter = isPreferred === '1';
            else if (filter === 'overdue') matchesFilter = overdue > 0;

            if (matchesSearch && matchesFilter) {
                card.classList.remove('d-none');
                visibleCards.push(card);
            } else {
                card.classList.add('d-none');
            }
        });

        const sortBy = supplierSort?.value || 'name';
        const container = document.getElementById('supplierCardsContainer');
        if (container) {
            visibleCards.sort((a, b) => {
                if (sortBy === 'name') return (a.dataset.name || '').localeCompare(b.dataset.name || '');
                if (sortBy === 'spend') return parseInt(b.dataset.spend || 0) - parseInt(a.dataset.spend || 0);
                if (sortBy === 'ontime') return parseFloat(b.dataset.ontime || 0) - parseFloat(a.dataset.ontime || 0);
                if (sortBy === 'recent') {
                    const dateA = a.dataset.lastorder === 'N/A' ? '0000-00-00' : a.dataset.lastorder;
                    const dateB = b.dataset.lastorder === 'N/A' ? '0000-00-00' : b.dataset.lastorder;
                    return dateB.localeCompare(dateA);
                }
                return 0;
            });
            visibleCards.forEach(card => container.appendChild(card));
        }

        if (supplierNoResults) supplierNoResults.classList.toggle('d-none', visibleCards.length > 0);
        if (supplierCountBadge) supplierCountBadge.textContent = visibleCards.length;
    }

    supplierSearch?.addEventListener('input', applySupplierFilters);
    supplierFilter?.addEventListener('change', applySupplierFilters);
    supplierSort?.addEventListener('change', applySupplierFilters);

    // ─── Edit Supplier Modal ───
    const editSupplierModal = document.getElementById('editSupplierModal');
    if (editSupplierModal) {
        document.querySelectorAll('.edit-supplier-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.dataset.id;
                document.getElementById('editSupplierForm').action = `/inventory/suppliers/${id}/edit`;
                document.getElementById('editSupName').value = btn.dataset.name || '';
                document.getElementById('editSupContact').value = btn.dataset.contact || '';
                document.getElementById('editSupPhone').value = btn.dataset.phone || '';
                document.getElementById('editSupEmail').value = btn.dataset.email || '';
                document.getElementById('editSupAddress').value = btn.dataset.address || '';
                document.getElementById('editSupNotes').value = btn.dataset.notes || '';
                document.getElementById('editSupPreferred').value = btn.dataset.preferred || '0';
                document.getElementById('editSupActive').value = btn.dataset.active || '1';
                document.getElementById('editSupImagePath').value = btn.dataset.image || '';

                new bootstrap.Modal(editSupplierModal).show();
            });
        });
    }

    // ─── Supplier Detail Modal (AJAX) ───
    const supplierDetailModal = document.getElementById('supplierDetailModal');
    if (supplierDetailModal) {
        document.querySelectorAll('.view-supplier-detail-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.dataset.id;
                const loadingEl = document.getElementById('supplierDetailLoading');
                const contentEl = document.getElementById('supplierDetailContent');
                loadingEl.classList.remove('d-none');
                contentEl.classList.add('d-none');

                new bootstrap.Modal(supplierDetailModal).show();

                fetch(`/inventory/suppliers/${id}`)
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('supplierDetailName').textContent = data.name;
                        document.getElementById('sdContact').textContent = data.contact_name || '—';
                        document.getElementById('sdPhoneEmail').textContent = `${data.phone || '—'} / ${data.email || '—'}`;
                        document.getElementById('sdAddress').textContent = data.address || '—';
                        document.getElementById('sdCreatedAt').textContent = data.created_at || '—';
                        document.getElementById('sdNotes').textContent = data.notes || 'No notes.';
                        document.getElementById('sdTotalSpend').textContent = `$${(data.total_spend_cents / 100).toFixed(2)}`;
                        document.getElementById('sdOpenPOs').textContent = data.open_pos_count;
                        document.getElementById('sdIngredientCount').textContent = data.ingredients_supplied.length;

                        // Ingredients pills
                        const ingList = document.getElementById('sdIngredientsList');
                        ingList.innerHTML = '';
                        if (data.ingredients_supplied.length === 0) {
                            ingList.innerHTML = '<span class="text-secondary small">None yet.</span>';
                        } else {
                            data.ingredients_supplied.forEach(ing => {
                                ingList.innerHTML += `<span class="badge bg-dark border border-secondary text-light">${ing.name} <span class="text-secondary">(${ing.unit})</span></span>`;
                            });
                        }

                        // PO History table
                        const poBody = document.getElementById('sdPOTableBody');
                        poBody.innerHTML = '';
                        if (data.recent_pos.length === 0) {
                            poBody.innerHTML = '<tr><td colspan="5" class="text-center text-secondary">No orders yet.</td></tr>';
                        } else {
                            const statusColors = {
                                'draft': 'secondary', 'approved': 'info', 'ordered': 'primary',
                                'partially_received': 'warning', 'received': 'success', 'cancelled': 'danger'
                            };
                            data.recent_pos.forEach(po => {
                                const color = statusColors[po.status] || 'secondary';
                                poBody.innerHTML += `
                                    <tr>
                                        <td class="font-monospace text-emerald">${po.po_number}</td>
                                        <td><span class="badge bg-${color} bg-opacity-20 text-${color} border border-${color}">${po.status}</span></td>
                                        <td>${po.created_at}</td>
                                        <td>${po.expected_at || '—'}</td>
                                        <td class="fw-bold">$${(po.total_cents / 100).toFixed(2)}</td>
                                    </tr>
                                `;
                            });
                        }

                        loadingEl.classList.add('d-none');
                        contentEl.classList.remove('d-none');
                    })
                    .catch(err => {
                        loadingEl.innerHTML = `<p class="text-danger">Failed to load supplier details.</p>`;
                    });
            });
        });
    }

    // ─── New PO for Supplier Shortcut ───
    document.querySelectorAll('.new-po-for-supplier-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const supplierId = btn.dataset.supplierId;
            const purchasingTab = document.getElementById('purchasing-tab');
            if (purchasingTab) {
                new bootstrap.Tab(purchasingTab).show();
            }
            setTimeout(() => {
                const createOrderModal = document.getElementById('createOrderModal');
                if (createOrderModal) {
                    const supplierSelect = createOrderModal.querySelector('[name="supplier_id"]');
                    if (supplierSelect) supplierSelect.value = supplierId;
                    new bootstrap.Modal(createOrderModal).show();
                }
            }, 300);
        });
    });

});
