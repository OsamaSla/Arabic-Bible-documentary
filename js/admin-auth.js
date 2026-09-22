/**
 * Arabic Christian Translations - Admin Authentication
 * Simple session-based admin login
 */

var AdminAuth = {
    // Default credentials - CHANGE THESE!
    username: 'admin',
    password: 'admin123',
    sessionKey: 'admin_logged_in',
    
    init: function() {
        // Check if user is already logged in
        if (this.isLoggedIn()) {
            // Redirect to admin panel if logged in
            window.location.href = 'admin-panel.html';
        }
    },
    
    login: function(username, password) {
        if (username === this.username && password === this.password) {
            sessionStorage.setItem(this.sessionKey, 'true');
            return true;
        }
        return false;
    },
    
    logout: function() {
        sessionStorage.removeItem(this.sessionKey);
        window.location.href = 'admin.html';
    },
    
    isLoggedIn: function() {
        return sessionStorage.getItem(this.sessionKey) === 'true';
    }
};

// Initialize auth when DOM loads
AdminAuth.init();
