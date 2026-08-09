package main

import (
	"fmt"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Config defines the process boundary between the Go edge and Python API.
type Config struct {
	ListenAddr  string
	BackendURL  string
	StaticDir   string
	AllowRemote bool
}

// Server serves immutable frontend files and forwards the stateful API.
type Server struct {
	config    Config
	staticDir string
	indexPath string
	apiProxy  *httputil.ReverseProxy
}

// NewServer validates configuration and constructs an edge handler.
func NewServer(config Config) (*Server, error) {
	if strings.TrimSpace(config.ListenAddr) == "" {
		return nil, usageError("listen address must not be empty")
	}
	if err := validateListenAddr(config.ListenAddr, config.AllowRemote); err != nil {
		return nil, err
	}
	backend, err := parseBackendURL(config.BackendURL)
	if err != nil {
		return nil, err
	}

	staticDir, err := filepath.Abs(config.StaticDir)
	if err != nil {
		return nil, fmt.Errorf("resolve static directory: %w", err)
	}
	staticDir, err = filepath.EvalSymlinks(staticDir)
	if err != nil {
		return nil, fmt.Errorf("resolve static directory %q: %w", config.StaticDir, err)
	}
	info, err := os.Stat(staticDir)
	if err != nil {
		return nil, fmt.Errorf("stat static directory %q: %w", staticDir, err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("static path %q is not a directory", staticDir)
	}
	indexPath := filepath.Join(staticDir, "index.html")
	indexInfo, err := os.Stat(indexPath)
	if err != nil {
		return nil, fmt.Errorf("stat SPA entrypoint %q: %w", indexPath, err)
	}
	if indexInfo.IsDir() {
		return nil, fmt.Errorf("SPA entrypoint %q is a directory", indexPath)
	}

	return &Server{
		config:    config,
		staticDir: staticDir,
		indexPath: indexPath,
		apiProxy:  httputil.NewSingleHostReverseProxy(backend),
	}, nil
}

func validateListenAddr(raw string, allowRemote bool) error {
	host, port, err := net.SplitHostPort(raw)
	if err != nil {
		return usageError("listen address must be host:port: %v", err)
	}
	portNumber, err := strconv.Atoi(port)
	if err != nil || portNumber < 1 || portNumber > 65535 {
		return usageError("listen port must be between 1 and 65535")
	}
	if allowRemote || isLoopbackHost(host) {
		return nil
	}
	return usageError("refusing non-loopback listen address %q without allow-remote", raw)
}

func isLoopbackHost(host string) bool {
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

func parseBackendURL(raw string) (*url.URL, error) {
	value := strings.TrimSpace(raw)
	if value == "" {
		return nil, usageError("backend URL must not be empty")
	}
	backend, err := url.Parse(value)
	if err != nil {
		return nil, usageError("invalid backend URL: %v", err)
	}
	if backend.Scheme != "http" && backend.Scheme != "https" {
		return nil, usageError("backend URL scheme must be http or https")
	}
	if backend.Host == "" {
		return nil, usageError("backend URL must include a host")
	}
	if backend.User != nil {
		return nil, usageError("backend URL must not include credentials")
	}
	return backend, nil
}

// ServeHTTP keeps API authentication and authorization in the Python service.
// All request headers, including Authorization and Cookie, are retained by the
// standard reverse proxy so browser sessions and API clients remain compatible.
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	setSecurityHeaders(w)
	if isAPIPath(r.URL.Path) {
		s.apiProxy.ServeHTTP(w, r)
		return
	}
	s.serveStatic(w, r)
}

func setSecurityHeaders(w http.ResponseWriter) {
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("X-Frame-Options", "DENY")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set(
		"Content-Security-Policy",
		"default-src 'self'; "+
			"script-src 'self'; "+
			"style-src 'self' 'unsafe-inline'; "+
			"img-src 'self' data: blob:; "+
			"connect-src 'self'; "+
			"frame-src 'self' about: data: blob:; "+
			"frame-ancestors 'none'; "+
			"base-uri 'self'; "+
			"form-action 'self'",
	)
}

func isAPIPath(path string) bool {
	return path == "/api" || strings.HasPrefix(path, "/api/")
}

func (s *Server) serveStatic(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	path := s.staticPath(r.URL.Path)
	if path == "" {
		path = s.indexPath
	}
	if path == s.indexPath {
		// ServeFile rejects URL paths containing ".." before it considers the
		// filesystem path. The filesystem path is already constrained above, so
		// pass a sanitized URL while serving the SPA fallback as well.
		safeRequest := r.Clone(r.Context())
		safeURL := *r.URL
		safeURL.Path = "/"
		safeURL.RawPath = ""
		safeRequest.URL = &safeURL
		r = safeRequest
	}
	http.ServeFile(w, r, path)
}

// staticPath returns a file only when it remains inside the configured static
// root, including after symlink resolution. Missing assets fall back to the
// SPA entrypoint so client-side routes continue to work.
func (s *Server) staticPath(requestPath string) string {
	relative := strings.TrimPrefix(requestPath, "/")
	if relative == "" || strings.IndexByte(relative, 0) >= 0 {
		return ""
	}

	candidate := filepath.Join(s.staticDir, filepath.FromSlash(relative))
	resolved, err := filepath.EvalSymlinks(candidate)
	if err != nil {
		return s.indexPath
	}
	if !isWithin(s.staticDir, resolved) {
		return s.indexPath
	}
	info, err := os.Stat(resolved)
	if err != nil || info.IsDir() {
		return s.indexPath
	}
	return resolved
}

func isWithin(root, candidate string) bool {
	relative, err := filepath.Rel(root, candidate)
	if err != nil {
		return false
	}
	return relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator)) && relative != "."
}
