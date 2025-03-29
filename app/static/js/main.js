/**
 * SciLit Hauptskript
 * Enthält gemeinsame Funktionen, die auf allen Seiten benötigt werden
 */

// Sofort ausgeführte Funktion, um den globalen Namespace nicht zu verschmutzen
(function() {
    'use strict';
    
    /**
     * Hauptinitialisierungsfunktion, die beim Laden der Seite ausgeführt wird
     */
    function initApp() {
        console.log('SciLit App initialisiert');
        
        // Allgemeine Funktionen für alle Seiten
        setupMobileNavigation();
        setupCollapsibleSections();
        setupFooterDate();
        
        // Seiten-spezifische Funktionalität basierend auf Pfad
        const path = window.location.pathname;
        
        if (path === '/' || path.endsWith('/index.html')) {
            // Homepage
            console.log('Homepage initialisiert');
        } else if (path.includes('/upload')) {
            // Upload-Seite
            document.dispatchEvent(new CustomEvent('scilit:uploadPage'));
        } else if (path.includes('/search')) {
            // Such-Seite
            document.dispatchEvent(new CustomEvent('scilit:searchPage'));
        } else if (path.includes('/documents') && !path.endsWith('/documents')) {
            // Dokumentendetails-Seite (enthält Dokumenten-ID)
            document.dispatchEvent(new CustomEvent('scilit:documentDetailPage'));
        } else if (path.endsWith('/documents')) {
            // Dokumentenliste-Seite
            document.dispatchEvent(new CustomEvent('scilit:documentsPage'));
        } else if (path.includes('/review-metadata')) {
            // Metadaten-Überprüfungsseite
            initReviewMetadataPage();
        }
    }
    
    /**
     * Richtet das mobile Navigationsmenü ein
     */
    function setupMobileNavigation() {
        const navToggle = document.querySelector('.nav-toggle');
        const nav = document.querySelector('nav');
        
        if (navToggle && nav) {
            navToggle.addEventListener('click', function() {
                nav.classList.toggle('open');
                
                // Aktualisiere Aria-Attribute für Barrierefreiheit
                const isExpanded = nav.classList.contains('open');
                navToggle.setAttribute('aria-expanded', isExpanded);
                nav.setAttribute('aria-hidden', !isExpanded);
            });
            
            // Schließe Navigationsmenü beim Klicken außerhalb
            document.addEventListener('click', function(event) {
                if (nav.classList.contains('open') && 
                    !nav.contains(event.target) && 
                    !navToggle.contains(event.target)) {
                    nav.classList.remove('open');
                    navToggle.setAttribute('aria-expanded', false);
                    nav.setAttribute('aria-hidden', true);
                }
            });
        }
    }
    
    /**
     * Richtet einklappbare/ausklappbare Abschnitte ein
     */
    function setupCollapsibleSections() {
        const toggleButtons = document.querySelectorAll('[data-toggle]');
        
        toggleButtons.forEach(button => {
            button.addEventListener('click', function() {
                const targetId = this.getAttribute('data-toggle');
                const targetElement = document.getElementById(targetId);
                
                if (targetElement) {
                    const isVisible = targetElement.style.display !== 'none';
                    
                    if (isVisible) {
                        targetElement.style.display = 'none';
                        this.innerHTML = this.innerHTML.replace('fa-chevron-up', 'fa-chevron-down');
                        this.setAttribute('aria-expanded', 'false');
                    } else {
                        targetElement.style.display = 'block';
                        this.innerHTML = this.innerHTML.replace('fa-chevron-down', 'fa-chevron-up');
                        this.setAttribute('aria-expanded', 'true');
                    }
                }
            });
        });
    }
    
    /**
     * Ersetzt Platzhalter für das aktuelle Jahr in der Fußzeile
     */
    function setupFooterDate() {
        const yearElement = document.querySelector('footer .container p');
        if (yearElement && yearElement.innerHTML.includes('{{ year }}')) {
            const year = new Date().getFullYear();
            yearElement.innerHTML = yearElement.innerHTML.replace('{{ year }}', year);
        }
    }
    
    /**
     * Hilfsfunktion zum Formatieren von Dateigrößen
     * @param {number} bytes - Dateigröße in Bytes
     * @returns {string} Formatierte Dateigröße (z.B. "1.23 MB")
     */
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    /**
     * Hilfsfunktion zur Fehlerbehandlung von AJAX-Anfragen
     * @param {Error} error - Fehlerobjekt
     * @param {string} context - Kontext der Anfrage
     */
    function handleAjaxError(error, context) {
        console.error(`Fehler bei ${context}:`, error);
        
        // Zeige Fehlermeldung
        showNotification(`Bei ${context} ist ein Fehler aufgetreten: ${error.message}`, 'error');
    }
    
    /**
     * Zeigt eine Benachrichtigung an
     * @param {string} message - Nachrichtentext
     * @param {string} type - Art der Nachricht (success, error, warning, info)
     * @param {number} duration - Dauer in Millisekunden
     */
    function showNotification(message, type = 'info', duration = 5000) {
        // Prüfe, ob ein Container für Benachrichtigungen existiert
        let notificationContainer = document.getElementById('notification-container');
        
        if (!notificationContainer) {
            notificationContainer = document.createElement('div');
            notificationContainer.id = 'notification-container';
            notificationContainer.style.position = 'fixed';
            notificationContainer.style.bottom = '20px';
            notificationContainer.style.right = '20px';
            notificationContainer.style.zIndex = '1000';
            document.body.appendChild(notificationContainer);
        }
        
        // Erstelle eine neue Benachrichtigung
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="close" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        
        // Füge die Benachrichtigung zum Container hinzu
        notificationContainer.appendChild(notification);
        
        // Füge Event-Handler für das Schließen hinzu
        const closeButton = notification.querySelector('.close');
        closeButton.addEventListener('click', function() {
            notification.remove();
        });
        
        // Entferne die Benachrichtigung nach der angegebenen Zeit
        if (duration > 0) {
            setTimeout(function() {
                notification.remove();
            }, duration);
        }
    }
    
    /**
     * Hilfsfunktion zum Senden einer AJAX-Anfrage
     * @param {string} url - URL der Anfrage
     * @param {Object} options - Optionen für fetch
     * @returns {Promise} Promise mit der Antwort
     */
    async function fetchWithErrorHandling(url, options = {}) {
        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                // Versuche, Fehlermeldung aus der Antwort zu extrahieren
                try {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || errorData.message || `HTTP-Fehler ${response.status}`);
                } catch (jsonError) {
                    // Wenn die Antwort kein gültiges JSON ist
                    throw new Error(`HTTP-Fehler ${response.status}`);
                }
            }
            
            return response;
        } catch (error) {
            // Füge der Fehlermeldung weitere Informationen hinzu
            error.url = url;
            error.requestOptions = options;
            throw error;
        }
    }
    
    /**
     * Prüft den Verarbeitungsstatus eines Dokuments
     * @param {string} docId - ID des Dokuments
     * @param {Function} statusCallback - Callback-Funktion für Statusaktualisierungen
     */
    function checkDocumentProcessing(docId, statusCallback) {
        // Abrufen des Dokumentenstatus vom Server
        fetch(`/api/document_status/${docId}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'complete') {
                // Wenn das Dokument vollständig verarbeitet wurde
                if (data.reload) {
                    // Wenn nötig, Seite neu laden
                    window.location.reload();
                } else if (statusCallback) {
                    // Callback mit dem Ergebnis aufrufen
                    statusCallback('complete', data.document);
                }
            } else {
                // Dokument ist noch in Verarbeitung
                if (statusCallback) {
                    statusCallback('processing', null);
                }
                // Nach 3 Sekunden erneut prüfen
                setTimeout(() => window.scilit.checkDocumentProcessing(docId, statusCallback), 3000);
            }
        })
        .catch(error => {
            console.error('Fehler beim Abrufen des Dokumentenstatus:', error);
            if (statusCallback) {
                statusCallback('error', null);
            }
        });
    }
    
    /**
     * Initialisiert die Metadaten-Überprüfungsseite
     */
    function initReviewMetadataPage() {
        // Polling für Verarbeitungsstatus einrichten
        const statusMessages = document.getElementById('status-messages');
        const processingStatus = document.getElementById('processing-status');
        
        if (processingStatus && processingStatus.style.display !== 'none') {
            // Liste aller Dokument-IDs sammeln
            const documentIds = [];
            const statusElements = document.querySelectorAll('[id^="status-"]');
            
            // Extrahiere die Dateinamen aus den Status-IDs
            statusElements.forEach(element => {
                const filename = element.id.replace('status-', '').replace(/-/g, '.');
                documentIds.push(filename);
            });
            
            // Polling-Funktion für den Status
            function checkProcessingStatus() {
                // Für jedes Dokument den Status prüfen
                documentIds.forEach(filename => {
                    fetch(`/api/document_status/${filename}`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Statusabfrage fehlgeschlagen');
                        }
                        return response.json();
                    })
                    .then(data => {
                        const statusElement = document.getElementById(`status-${filename.replace(/\./g, '-')}`);
                        if (!statusElement) return;
                        
                        if (data.status === 'complete') {
                            statusElement.classList.remove('pending');
                            statusElement.classList.add('success');
                            statusElement.innerHTML = `
                                <div class="status-message-icon">
                                    <i class="fas fa-check-circle"></i>
                                </div>
                                <div class="status-message-text">
                                    ${filename} wurde erfolgreich verarbeitet und in Ihre Bibliothek aufgenommen.
                                </div>
                            `;
                            
                            // Wenn alle erfolgreich, Navigation zu Dokumente anzeigen
                            const successElements = document.querySelectorAll('.success');
                            if (successElements.length === documentIds.length) {
                                const actionsElement = document.querySelector('.status-actions');
                                if (actionsElement) {
                                    actionsElement.style.display = 'flex';
                                }
                            }
                        }
                    })
                    .catch(error => console.error('Fehler beim Statusabruf:', error));
                });
                
                // Alle 3 Sekunden erneut prüfen, solange noch Dokumente verarbeitet werden
                const pendingElements = document.querySelectorAll('.pending');
                if (pendingElements.length > 0) {
                    setTimeout(checkProcessingStatus, 3000);
                }
            }
            
            // Starte das Polling
            checkProcessingStatus();
        }
    }
    
    // Mache einige Funktionen global verfügbar
    window.scilit = {
        formatFileSize,
        showNotification,
        fetchWithErrorHandling,
        checkDocumentProcessing
    };
    
    // Führe die Initialisierung nach dem Laden des DOM aus
    document.addEventListener('DOMContentLoaded', initApp);
    
})();