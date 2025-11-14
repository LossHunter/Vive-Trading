export default function Account() {
    const accountInfo = {
        name: "John Doe",
        email: "john.doe@example.com",
        role: "Admin"
    };

    return (
        <div className="account-container">
            <h2>Account Information</h2>
            <div className="account-item">
                <strong>Name:</strong> {accountInfo.name}
            </div>
            <div className="account-item">
                <strong>Email:</strong> {accountInfo.email}
            </div>
            <div className="account-item">
                <strong>Role:</strong> {accountInfo.role}
            </div>
            <button className="account-edit-btn">Edit Profile</button>
        </div>
    );
}
