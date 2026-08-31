# Use Nginx as the base image
FROM nginx:alpine

# Remove default Nginx config and HTML
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf

# Copy custom nginx config (listens on 8509 = PORT_BASE)
COPY web_application/nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend files into the Nginx web root
COPY web_application/index.html web_application/app.js web_application/styles.css /usr/share/nginx/html/

# Expose the app port
EXPOSE 8509

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
