class OCRProgress {
    constructor(formId) {
        this.form = document.getElementById(formId);
        this.progressBar = document.getElementById('progressBar');
        this.processingElement = document.getElementById('processingAnimation');
        this.submitButton = this.form.querySelector('button[type="submit"]');
        
        this.initEvents();
    }
    
    initEvents() {
        this.form.addEventListener('submit', (e) => {
            this.showProcessing();
            
            // Opcional: Usar AJAX para envio e acompanhamento de progresso
            // this.submitWithProgress(e);
        });
    }
    
    showProcessing() {
        this.submitButton.disabled = true;
        this.processingElement.style.display = 'flex';
        this.animateProgress();
    }
    
    animateProgress() {
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress >= 95) progress = 95; // Não chegar a 100% até conclusão
            
            this.progressBar.style.width = `${progress}%`;
            this.progressBar.setAttribute('aria-valuenow', progress);
            
            if (progress >= 100) {
                clearInterval(interval);
            }
        }, 500);
    }
    
    submitWithProgress(e) {
        e.preventDefault();
        
        const formData = new FormData(this.form);
        
        fetch(this.form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'complete') {
                this.progressBar.style.width = '100%';
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            }
        });
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    new OCRProgress('uploadForm');
});

// Em seu ocr_progress.js
document.addEventListener('DOMContentLoaded', function() {
    // Tratar erro de carregamento de imagem
    document.querySelectorAll('img').forEach(img => {
        img.onerror = function() {
            this.style.display = 'none';
            const parent = this.parentElement;
            if (parent) {
                const msg = document.createElement('p');
                msg.className = 'text-danger small';
                msg.textContent = 'Imagem não encontrada no servidor';
                parent.appendChild(msg);
            }
        };
    });
});

document.getElementById('faturaInput').addEventListener('change', function(e) {
    const file = e.target.files[0];
    const maxSize = 5 * 1024 * 1024; // 5MB
    
    if (file.size > maxSize) {
        alert('Arquivo muito grande. Tamanho máximo permitido: 5MB');
        e.target.value = ''; // Limpa o input
    }
});