// Command vulnclaw-edge is the first incremental Go migration seam.
//
// It serves the built SPA and proxies API requests to the existing Python
// backend. The Python agent runtime remains the source of truth for all
// stateful and security-sensitive application behavior.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

const (
	defaultListenAddr = "127.0.0.1:7789"
	defaultBackendURL = "http://127.0.0.1:7788"
)

func main() {
	listenAddr := flag.String("listen", defaultListenAddr, "address for the Go edge to listen on")
	backendURL := flag.String("backend", defaultBackendURL, "existing Python API base URL")
	staticDir := flag.String("static-dir", defaultStaticDir(), "directory containing the built SPA")
	allowRemote := flag.Bool("allow-remote", false, "allow binding to a non-loopback address")
	flag.Parse()

	server, err := NewServer(Config{
		ListenAddr:  *listenAddr,
		BackendURL:  *backendURL,
		StaticDir:   *staticDir,
		AllowRemote: *allowRemote,
	})
	if err != nil {
		log.Fatalf("configure vulnclaw-edge: %v", err)
	}

	httpServer := &http.Server{
		Addr:              server.config.ListenAddr,
		Handler:           server,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       30 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-stop
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := httpServer.Shutdown(ctx); err != nil {
			log.Printf("graceful shutdown failed: %v", err)
		}
	}()

	log.Printf("vulnclaw-edge listening on %s; API backend %s", server.config.ListenAddr, server.config.BackendURL)
	if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("serve vulnclaw-edge: %v", err)
	}
}

func defaultStaticDir() string {
	if info, err := os.Stat(filepath.FromSlash("frontend/dist")); err == nil && info.IsDir() {
		return filepath.FromSlash("frontend/dist")
	}
	return filepath.FromSlash("vulnclaw/web/static")
}

func usageError(format string, args ...any) error {
	return fmt.Errorf(format, args...)
}
