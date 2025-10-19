#!/bin/bash
# GTFS Batch Container Management Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Container name
CONTAINER_NAME="gtfs-batch"

# Help message
show_help() {
    echo "GTFS Batch Container Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build         Build the batch container image"
    echo "  start         Start the batch container (with cron jobs)"
    echo "  stop          Stop the batch container"
    echo "  restart       Restart the batch container"
    echo "  logs          Show container logs (tail -f)"
    echo "  logs-cron     Show cron job logs"
    echo "  logs-realtime    Show realtime fetch job logs"
    echo "  logs-predict  Show prediction job logs"
    echo "  logs-weather  Show weather scraper logs"
    echo "  logs-static   Show static load job logs"
    echo "  exec          Execute a command in the container"
    echo "  shell         Open a shell in the container"
    echo "  status        Show container status"
    echo "  run-job       Run a specific job manually (e.g., run-job load-realtime)"
    echo "  cron-list     List cron jobs configured in the container"
    echo "  clean         Stop and remove the container"
    echo "  rebuild       Clean, rebuild, and restart the container"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build                    # Build the container"
    echo "  $0 start                    # Start with automatic cron jobs"
    echo "  $0 logs                     # View container logs"
    echo "  $0 run-job load-realtime            # Manually run realtime fetch job"
    echo "  $0 run-job predict --dry-run # Run prediction in dry-run mode"
    echo "  $0 exec ls -la batch/logs   # Execute command in container"
    echo ""
}

# Check if container exists
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Build container
build_container() {
    echo -e "${BLUE}Building batch container...${NC}"
    docker-compose build batch
    echo -e "${GREEN}Build completed successfully!${NC}"
}

# Start container
start_container() {
    if container_running; then
        echo -e "${YELLOW}Container is already running.${NC}"
        return
    fi

    echo -e "${BLUE}Starting batch container...${NC}"
    docker-compose up -d batch

    echo -e "${GREEN}Container started successfully!${NC}"
    echo ""
    echo "Waiting for container to be ready..."
    sleep 5

    echo ""
    echo -e "${BLUE}Container status:${NC}"
    docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    echo ""
    echo -e "${GREEN}Cron jobs are now running.${NC}"
    echo "Use '$0 logs' to view logs."
}

# Stop container
stop_container() {
    if ! container_running; then
        echo -e "${YELLOW}Container is not running.${NC}"
        return
    fi

    echo -e "${BLUE}Stopping batch container...${NC}"
    docker-compose stop batch
    echo -e "${GREEN}Container stopped successfully!${NC}"
}

# Restart container
restart_container() {
    echo -e "${BLUE}Restarting batch container...${NC}"
    docker-compose restart batch
    echo -e "${GREEN}Container restarted successfully!${NC}"
}

# Show logs
show_logs() {
    if ! container_exists; then
        echo -e "${RED}Container does not exist. Run '$0 start' first.${NC}"
        exit 1
    fi

    echo -e "${BLUE}Showing container logs (Ctrl+C to exit)...${NC}"
    docker-compose logs -f batch
}

# Show cron logs
show_cron_logs() {
    if ! container_running; then
        echo -e "${RED}Container is not running.${NC}"
        exit 1
    fi

    echo -e "${BLUE}Showing cron logs (Ctrl+C to exit)...${NC}"
    docker exec -it ${CONTAINER_NAME} tail -f /app/batch/logs/cron_*.log
}

# Show specific job logs
show_job_logs() {
    local job_type=$1
    if ! container_running; then
        echo -e "${RED}Container is not running.${NC}"
        exit 1
    fi

    echo -e "${BLUE}Showing ${job_type} logs (Ctrl+C to exit)...${NC}"
    docker exec -it ${CONTAINER_NAME} sh -c "tail -f /app/batch/logs/cron_${job_type}.log /app/batch/logs/*${job_type}*.log 2>/dev/null || echo 'No logs found for ${job_type}'"
}

# Execute command in container
exec_command() {
    if ! container_running; then
        echo -e "${RED}Container is not running.${NC}"
        exit 1
    fi

    docker exec -it ${CONTAINER_NAME} "$@"
}

# Open shell
open_shell() {
    if ! container_running; then
        echo -e "${RED}Container is not running.${NC}"
        exit 1
    fi

    echo -e "${BLUE}Opening shell in container...${NC}"
    docker exec -it ${CONTAINER_NAME} /bin/bash
}

# Show status
show_status() {
    if ! container_exists; then
        echo -e "${RED}Container does not exist.${NC}"
        return
    fi

    echo -e "${BLUE}Container status:${NC}"
    docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    if container_running; then
        echo ""
        echo -e "${BLUE}Health check:${NC}"
        docker inspect ${CONTAINER_NAME} --format='{{.State.Health.Status}}' 2>/dev/null || echo "No health check configured"

        echo ""
        echo -e "${BLUE}Recent logs:${NC}"
        docker logs --tail 20 ${CONTAINER_NAME}
    fi
}

# Run specific job manually
run_job() {
    if ! container_running; then
        echo -e "${RED}Container is not running. Starting it now...${NC}"
        start_container
        sleep 3
    fi

    local job_name=$1
    shift
    local job_args="$@"

    echo -e "${BLUE}Running job: ${job_name} ${job_args}${NC}"
    docker exec -it ${CONTAINER_NAME} /usr/local/bin/python batch/run.py ${job_name} ${job_args}
}

# List cron jobs
list_cron_jobs() {
    if ! container_running; then
        echo -e "${RED}Container is not running.${NC}"
        exit 1
    fi

    echo -e "${BLUE}Configured cron jobs:${NC}"
    docker exec ${CONTAINER_NAME} cat /etc/cron.d/gtfs-batch
}

# Clean (stop and remove)
clean_container() {
    echo -e "${BLUE}Cleaning batch container...${NC}"
    docker-compose down batch 2>/dev/null || true
    echo -e "${GREEN}Container cleaned successfully!${NC}"
}

# Rebuild
rebuild_container() {
    echo -e "${BLUE}Rebuilding batch container...${NC}"
    clean_container
    build_container
    start_container
    echo -e "${GREEN}Rebuild completed successfully!${NC}"
}

# Main script logic
case "${1:-help}" in
    build)
        build_container
        ;;
    start)
        start_container
        ;;
    stop)
        stop_container
        ;;
    restart)
        restart_container
        ;;
    logs)
        show_logs
        ;;
    logs-cron)
        show_cron_logs
        ;;
    logs-realtime)
        show_job_logs "load-realtime"
        ;;
    logs-predict)
        show_job_logs "predict"
        ;;
    logs-weather)
        show_job_logs "weather"
        ;;
    logs-static)
        show_job_logs "static"
        ;;
    exec)
        shift
        exec_command "$@"
        ;;
    shell)
        open_shell
        ;;
    status)
        show_status
        ;;
    run-job)
        shift
        if [ -z "$1" ]; then
            echo -e "${RED}Error: Job name required.${NC}"
            echo "Available jobs: load-realtime, predict, scrape-weather, load-static"
            exit 1
        fi
        run_job "$@"
        ;;
    cron-list)
        list_cron_jobs
        ;;
    clean)
        clean_container
        ;;
    rebuild)
        rebuild_container
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac