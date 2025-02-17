if submit_request:
    # Build full breakdown details for the email (not shown in the UI)
    breakdown_info = f"""
Countertop Cost Estimator Details:
--------------------------------------------------
Slab: {selected_full_name}
Edge Profile: {selected_edge_profile}
Square Footage: {sq_ft_needed}
Slab Sq Ft: {costs['available_sq_ft']:.2f} sq.ft
Serial Number: {costs['serial_number']}
Material & Fab: ${costs['material_and_fab']:,.2f}
Installation: ${costs['install_cost']:,.2f}
IB: ${costs['ib_cost']:,.2f}
Subtotal (before tax): ${sub_total:,.2f}
GST (5%): ${gst_amount:,.2f}
Final Price: ${final_price:,.2f}
--------------------------------------------------
"""
    customer_info = f"""
Customer Information:
--------------------------------------------------
Name: {str(name)}
Email: {str(email)}
Phone: {str(phone)}
Address: {str(address)}
City: {str(city)}
Postal Code: {str(postal_code)}
Sales Person: {str(sales_person)}
--------------------------------------------------
"""
    email_body = f"New Countertop Request:\n\n{customer_info}\n\n{breakdown_info}"
    subject = f"New Countertop Request from {name}"
    if send_email(subject, email_body):
        st.success("Your request has been submitted successfully! We will contact you soon.")
        st.experimental_rerun()  # Clear the form by re-running the app
    else:
        st.error("Failed to send email. Please try again later.")