// Main JavaScript file for Lihi's Assistant

// Form validation
(function() {
    'use strict';
    
    // Bootstrap form validation
    window.addEventListener('load', function() {
        const forms = document.getElementsByClassName('needs-validation');
        const validation = Array.prototype.filter.call(forms, function(form) {
            form.addEventListener('submit', function(event) {
                if (form.checkValidity() === false) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);
        });
    }, false);
})();

// Utility functions
function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleDateString('he-IL', options);
}

// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Add animation classes on scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '0';
            entry.target.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                entry.target.style.transition = 'all 0.6s ease-out';
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }, 100);
            
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe all cards
document.querySelectorAll('.card').forEach(card => {
    observer.observe(card);
});

// Auto-hide alerts
document.querySelectorAll('.alert-dismissible').forEach(alert => {
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
    }, 5000);
});

// Character counter for textareas
document.querySelectorAll('textarea[minlength], textarea[maxlength]').forEach(textarea => {
    const minLength = textarea.getAttribute('minlength');
    const maxLength = textarea.getAttribute('maxlength');
    
    if (minLength || maxLength) {
        const counter = document.createElement('small');
        counter.className = 'text-muted float-end mt-1';
        textarea.parentElement.appendChild(counter);
        
        function updateCounter() {
            const length = textarea.value.length;
            let text = `${length} תווים`;
            
            if (minLength && length < minLength) {
                text += ` (מינימום ${minLength})`;
                counter.classList.add('text-danger');
                counter.classList.remove('text-muted');
            } else if (maxLength && length > maxLength) {
                text += ` (מקסימום ${maxLength})`;
                counter.classList.add('text-danger');
                counter.classList.remove('text-muted');
            } else {
                counter.classList.remove('text-danger');
                counter.classList.add('text-muted');
            }
            
            counter.textContent = text;
        }
        
        textarea.addEventListener('input', updateCounter);
        updateCounter();
    }
});

// Tooltip initialization
const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Prevent double form submission
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function() {
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            const originalText = submitButton.innerHTML;
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>מעבד...';
            
            // Re-enable after 10 seconds (fallback)
            setTimeout(() => {
                submitButton.disabled = false;
                submitButton.innerHTML = originalText;
            }, 10000);
        }
    });
});

// Copy to clipboard functionality
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Show success toast
        showToast('הטקסט הועתק ללוח');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('שגיאה בהעתקה', 'error');
    });
}

// Toast notifications
function showToast(message, type = 'success') {
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0" 
             role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    toastContainer.innerHTML = toastHtml;
    document.body.appendChild(toastContainer);
    
    const toast = new bootstrap.Toast(toastContainer.querySelector('.toast'));
    toast.show();
    
    // Remove container after toast is hidden
    toastContainer.querySelector('.toast').addEventListener('hidden.bs.toast', () => {
        toastContainer.remove();
    });
}

// Patient Manager functionality
window.openPatientManager = function() {
    const modal = new bootstrap.Modal(document.getElementById('patientManagerModal'));
    modal.show();
    loadPatients();
};

async function loadPatients() {
    const loadingDiv = document.getElementById('patientsLoading');
    const listDiv = document.getElementById('patientsList');
    const emptyDiv = document.getElementById('patientsEmpty');
    
    // Show loading
    loadingDiv.classList.remove('d-none');
    listDiv.classList.add('d-none');
    emptyDiv.classList.add('d-none');
    
    try {
        const response = await fetch('/api/patients');
        const data = await response.json();
        
        // Hide loading
        loadingDiv.classList.add('d-none');
        
        if (data.patients && data.patients.length > 0) {
            displayPatients(data.patients);
            listDiv.classList.remove('d-none');
        } else {
            emptyDiv.classList.remove('d-none');
        }
    } catch (error) {
        console.error('Error loading patients:', error);
        loadingDiv.classList.add('d-none');
        emptyDiv.classList.remove('d-none');
        document.querySelector('#patientsEmpty p').textContent = 'שגיאה בטעינת מטופלים';
    }
}

function displayPatients(patients) {
    const listDiv = document.getElementById('patientsList');
    listDiv.innerHTML = '';
    
    patients.forEach(patient => {
        const patientRow = document.createElement('div');
        patientRow.className = 'row align-items-center py-2 border-bottom';
        patientRow.innerHTML = `
            <div class="col-md-4">
                <strong>${patient.name}</strong>
            </div>
            <div class="col-md-4 text-muted">
                מזהה: ${patient.id}
            </div>
            <div class="col-md-4 text-end">
                <button class="btn btn-sm btn-outline-danger" onclick="deletePatient('${patient.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        listDiv.appendChild(patientRow);
    });
}

// Add patient form handler
document.addEventListener('DOMContentLoaded', function() {
    const addPatientForm = document.getElementById('addPatientForm');
    if (addPatientForm) {
        addPatientForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const patientId = document.getElementById('newPatientId').value;
            const patientName = document.getElementById('newPatientName').value;
            
            if (!patientId || !patientName) {
                showToast('נא למלא את כל השדות', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/patients', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        patient_id: patientId,
                        patient_name: patientName
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to add patient');
                }
                
                // Clear form
                document.getElementById('newPatientId').value = '';
                document.getElementById('newPatientName').value = '';
                
                // Reload patients list
                loadPatients();
                
                showToast('מטופל נוסף בהצלחה!');
                
            } catch (error) {
                console.error('Error adding patient:', error);
                showToast('שגיאה בהוספת מטופל', 'error');
            }
        });
    }
});

window.deletePatient = async function(patientId) {
    if (!confirm('האם את בטוחה שברצונך למחוק את המטופל? פעולה זו לא ניתנת לביטול.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/patients/${patientId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete patient');
        }
        
        // Reload patients list
        loadPatients();
        
        showToast('מטופל נמחק בהצלחה');
        
    } catch (error) {
        console.error('Error deleting patient:', error);
        showToast('שגיאה במחיקת מטופל', 'error');
    }
};

// Export functions for use in other scripts
window.therapyApp = {
    formatDate,
    copyToClipboard,
    showToast
};