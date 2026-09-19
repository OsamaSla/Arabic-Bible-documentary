/**
 * Admin Authentication - Client-side auth for static sites
 * Password is stored as SHA-256 hash
 */

var AdminAuth = {
    // Default credentials - CHANGE THESE!
    // Hash generated with: sha256('admin123')
    defaultHash: '240be518fabd2724ddb6f05ee70ba245a77e8f641b81cd5320420437e9ca136e',
    username: 'admin',
    sessionKey: 'admin_logged_in',
    
    init: function() {
        var loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', this.handleLogin.bind(this));
        }
    },
    
    handleLogin: function(e) {
        e.preventDefault();
        var username = document.getElementById('username').value;
        var password = document.getElementById('password').value;
        
        if (this.authenticate(username, password)) {
            sessionStorage.setItem(this.sessionKey, 'true');
            window.location.href = 'admin-panel.html';
        } else {
            document.getElementById('loginError').style.display = 'block';
        }
    },
    
    authenticate: function(username, password) {
        if (username !== this.username) return false;
        
        // Simple SHA-256 hash comparison
        var hash = this.sha256(password);
        return hash === this.defaultHash;
    },
    
    isLoggedIn: function() {
        return sessionStorage.getItem(this.sessionKey) === 'true';
    },
    
    logout: function() {
        sessionStorage.removeItem(this.sessionKey);
        window.location.href = 'admin.html';
    },
    
    // Simple SHA-256 implementation
    sha256: function(message) {
        var msgBuffer = new TextEncoder().encode(message);
        var hashBuffer = crypto.subtle.digest('SHA-256', msgBuffer);
        var hashArray = Array.from(new Uint8Array(hashBuffer));
        var hashHex = hashArray.map(function(b) { return b.toString(16).padStart(2, '0'); }).join('');
        return hashHex;
    }
};

document.addEventListener('DOMContentLoaded', function() {
    AdminAuth.init();
});
