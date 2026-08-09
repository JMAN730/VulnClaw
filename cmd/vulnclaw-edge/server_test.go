package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestParseBackendURLRejectsUnsafeValues(t *testing.T) {
	for _, raw := range []string{
		"",
		"ftp://127.0.0.1:7788",
		"http://",
		"http://user:password@127.0.0.1:7788",
	} {
		if _, err := parseBackendURL(raw); err == nil {
			t.Errorf("parseBackendURL(%q) accepted an unsafe value", raw)
		}
	}
}

func TestValidateListenAddrRequiresExplicitRemoteOptIn(t *testing.T) {
	for _, raw := range []string{"0.0.0.0:7789", ":7789", "10.0.0.5:7789"} {
		if err := validateListenAddr(raw, false); err == nil {
			t.Errorf("validateListenAddr(%q, false) accepted a remote bind", raw)
		}
		if err := validateListenAddr(raw, true); err != nil {
			t.Errorf("validateListenAddr(%q, true) error = %v", raw, err)
		}
	}
	for _, raw := range []string{"127.0.0.1:7789", "[::1]:7789", "localhost:7789"} {
		if err := validateListenAddr(raw, false); err != nil {
			t.Errorf("validateListenAddr(%q, false) error = %v", raw, err)
		}
	}
}

func TestServerProxiesAPIAndPreservesBrowserCredentials(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/tasks" {
			t.Errorf("backend path = %q, want /api/tasks", r.URL.Path)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer test-token" {
			t.Errorf("authorization = %q, want bearer token", got)
		}
		if got := r.Header.Get("Cookie"); got != "vulnclaw_session=test-session" {
			t.Errorf("cookie = %q, want session cookie", got)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	}))
	defer backend.Close()

	staticDir := makeStaticDir(t)
	server, err := NewServer(Config{ListenAddr: "127.0.0.1:7789", BackendURL: backend.URL, StaticDir: staticDir})
	if err != nil {
		t.Fatalf("NewServer() error = %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "http://edge.test/api/tasks", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	req.Header.Set("Cookie", "vulnclaw_session=test-session")
	resp := httptest.NewRecorder()
	server.ServeHTTP(resp, req)

	if resp.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want %d", resp.Code, http.StatusAccepted)
	}
	if got := resp.Header().Get("X-Content-Type-Options"); got != "nosniff" {
		t.Errorf("X-Content-Type-Options = %q, want nosniff", got)
	}
	if got := strings.TrimSpace(resp.Body.String()); got != `{"status":"ok"}` {
		t.Errorf("body = %q", got)
	}
}

func TestServerServesAssetsAndSPAOnlyForSafeStaticPaths(t *testing.T) {
	staticDir := makeStaticDir(t)
	if err := os.Mkdir(filepath.Join(staticDir, "assets"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(staticDir, "assets", "app.js"), []byte("console.log('ok')"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(t.TempDir(), "secret.txt"), []byte("secret"), 0o644); err != nil {
		t.Fatal(err)
	}

	server, err := NewServer(Config{ListenAddr: "127.0.0.1:7789", BackendURL: "http://127.0.0.1:7788", StaticDir: staticDir})
	if err != nil {
		t.Fatalf("NewServer() error = %v", err)
	}

	tests := []struct {
		name       string
		method     string
		path       string
		wantStatus int
		wantBody   string
	}{
		{name: "asset", method: http.MethodGet, path: "/assets/app.js", wantStatus: http.StatusOK, wantBody: "console.log('ok')"},
		{name: "spa route", method: http.MethodGet, path: "/reports/123", wantStatus: http.StatusOK, wantBody: "<!doctype html>"},
		{name: "traversal fallback", method: http.MethodGet, path: "/%2e%2e/secret.txt", wantStatus: http.StatusOK, wantBody: "<!doctype html>"},
		{name: "post rejected", method: http.MethodPost, path: "/", wantStatus: http.StatusMethodNotAllowed, wantBody: "method not allowed"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			req := httptest.NewRequest(test.method, "http://edge.test"+test.path, nil)
			resp := httptest.NewRecorder()
			server.ServeHTTP(resp, req)
			if resp.Code != test.wantStatus {
				t.Fatalf("status = %d, want %d", resp.Code, test.wantStatus)
			}
			if got := resp.Header().Get("Content-Security-Policy"); got == "" {
				t.Error("Content-Security-Policy header is missing")
			}
			if !strings.Contains(resp.Body.String(), test.wantBody) {
				t.Errorf("body %q does not contain %q", resp.Body.String(), test.wantBody)
			}
		})
	}
}

func makeStaticDir(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "index.html"), []byte("<!doctype html><html>SPA</html>"), 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}
